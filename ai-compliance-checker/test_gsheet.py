from google_sheets_helper import connect_to_sheet, write_missing_clauses

sheet = connect_to_sheet()

write_missing_clauses(
    sheet,
    "TEST FILE.docx",
    ["Confidentiality", "Data Processing Agreement"]
)

print("✅ Google Sheets write test completed!")