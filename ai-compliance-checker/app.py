# app.py
import os
from datetime import datetime
from flask import (
    Flask, render_template, request, send_file,
    redirect, url_for, session, flash, jsonify
)
from dotenv import load_dotenv
from compliance_logic import read_docx, check_compliance, modify_docx
from email_smtp import send_email

# Google Sheets (optional)
import gspread
from google.oauth2.service_account import Credentials

# Load .env from same folder as this file
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

UPLOAD_FOLDER = "contracts"
MODIFIED_FOLDER = "modified"

app = Flask(__name__, static_folder="static", template_folder="templates")
# secret key for session (theme stored in session)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-please-change")

# small site config used in templates
app.config["SITE_OWNER"] = os.getenv("SITE_OWNER", "You")

# make sure upload folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MODIFIED_FOLDER, exist_ok=True)

# In-memory history store (A: store only in memory)
# Each entry: {id, original_filename, saved_filename, updated_filename, missing, timestamp, email_status, sheet_status}
app_history = []

# Make os and config available in templates (avoids UndefinedError for os/config)
app.jinja_env.globals["os"] = os
app.jinja_env.globals["config"] = app.config

# Helper: write to Google Sheets (kept same behaviour)
def write_to_google_sheet(original_file, missing_clauses, email_status):
    try:
        if os.getenv("GOOGLE_SHEETS_ENABLED") != "true":
            return "Google Sheets logging disabled"

        credentials_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        sheet_tab = os.getenv("GOOGLE_SHEET_TAB")

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(sheet_id).worksheet(sheet_tab)

        missing_text = ", ".join(missing_clauses) if missing_clauses else "No missing clauses"

        sheet.append_row([
            original_file,
            missing_text,
            email_status,
        ])

        return "Logged to Google Sheets"

    except Exception as e:
        return f"Google Sheets Error: {str(e)}"


# Context processor to expose theme and a few convenient items to templates
@app.context_processor
def inject_template_defaults():
    theme = session.get("theme", os.getenv("DEFAULT_THEME", "dark"))  # B: theme stored in session
    return {
        "current_theme": theme,
        "updated_filename": (app_history[-1]["updated_filename"] if app_history else None),
        "email_status_global": (app_history[-1]["email_status"] if app_history else None),
        "sheet_status_global": (app_history[-1]["sheet_status"] if app_history else None),
    }


@app.route("/")
def index():
    # upload_page.html (templates were renamed by you)
    return render_template("upload_page.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        flash("Empty filename", "danger")
        return redirect(url_for("index"))

    # Save uploaded file
    saved_filename = file.filename
    saved_path = os.path.join(UPLOAD_FOLDER, saved_filename)

    # If a file with same name exists, add timestamp suffix to avoid permission/overwrite issues
    if os.path.exists(saved_path):
        base, ext = os.path.splitext(saved_filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_filename = f"{base}_{timestamp}{ext}"
        saved_path = os.path.join(UPLOAD_FOLDER, saved_filename)

    file.save(saved_path)

    # Read and analyze
    content = read_docx(saved_path)
    missing = check_compliance(content)

    # Prepare modified file
    modified_filename = saved_filename.replace(".docx", "_modified.docx")
    modified_path = os.path.join(MODIFIED_FOLDER, modified_filename)
    modify_docx(saved_path, modified_path, missing)

    # Prepare textual missing summary
    if missing:
        missing_text = "\n".join(f"- {m}" for m in missing)
    else:
        missing_text = "✅ No missing clauses — fully compliant."

    # Email body
    email_message = f"""Hello {os.getenv('EMAIL_TEAM_NAME') or 'Team'},

Contract checked: {saved_filename}

Missing clauses:
{missing_text}

Modified contract is available for download.

Regards,
Compliance Checker AI System
"""

    # Send email (safe wrapped)
    try:
        recipients_env = os.getenv("EMAIL_TO") or ""
        recipients = [r.strip() for r in recipients_env.split(",") if r.strip()]
        if not recipients:
            email_status = {"status": "no_recipients", "message": "No recipients configured"}
        else:
            send_result = send_email(
                subject="Compliance Checker Update",
                body=email_message,
                recipients=recipients,
                smtp_server=os.getenv("EMAIL_SMTP_HOST") or os.getenv("EMAIL_HOST"),
                smtp_port=int(os.getenv("EMAIL_SMTP_PORT") or os.getenv("EMAIL_PORT") or 587),
                smtp_user=os.getenv("EMAIL_FROM"),
                smtp_password=os.getenv("EMAIL_PASSWORD"),
            )
            # Expect send_email to return a dict or similar; normalize
            if isinstance(send_result, dict):
                email_status = send_result
            else:
                # If send_email returns True/False/string, wrap it
                email_status = {"status": "sent" if send_result else "error", "message": str(send_result)}
    except Exception as e:
        email_status = {"status": "error", "message": str(e)}

    # Log to Google Sheets (optional)
    sheet_status = write_to_google_sheet(saved_filename, missing, email_status)

    # Add to in-memory history (A: store only in memory)
    history_entry = {
        "id": len(app_history) + 1,
        "original_filename": saved_filename,
        "saved_filename": saved_filename,
        "updated_filename": modified_filename,
        "missing": missing,
        "timestamp": datetime.now().isoformat(),
        "email_status": email_status,
        "sheet_status": sheet_status,
    }
    app_history.insert(0, history_entry)  # newest first

    # Render analysis_output.html
    return render_template(
        "analysis_output.html",
        original_filename=saved_filename,
        saved_filename=saved_filename,
        updated_filename=modified_filename,
        missing=missing,
        email_status=email_status,
        sheet_status=sheet_status
    )


@app.route("/download/uploads/<path:filename>")
def download_upload(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(path, as_attachment=True)


@app.route("/download/updated/<path:filename>")
def download_modified(filename):
    path = os.path.join(MODIFIED_FOLDER, filename)
    return send_file(path, as_attachment=True)


# History page (shows in-memory runs)
@app.route("/history")
def history_page():
    return render_template("history_page.html", history=app_history)


# Settings page: GET shows current theme, POST toggles/stores theme in session (B: theme in session)
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        selected_theme = request.form.get("theme")
        if selected_theme in ("dark", "light"):
            session["theme"] = selected_theme
            flash(f"Theme changed to {selected_theme}", "success")
        else:
            flash("Invalid theme selection", "danger")
        return redirect(url_for("settings"))

    current_theme = session.get("theme", os.getenv("DEFAULT_THEME", "dark"))
    return render_template("settings_page.html", current_theme=current_theme)


# Simple API: toggle theme (AJAX-friendly)
@app.route("/set-theme/<mode>")
def set_theme(mode):
    if mode in ["light", "dark"]:
        session["theme"] = mode
    return redirect(request.referrer or "/settings")



if __name__ == "__main__":
    # debug mode for local development
    app.run(debug=True, host="127.0.0.1", port=int(os.getenv("PORT", 5000)))
