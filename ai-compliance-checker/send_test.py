from email_smtp import send_email_smtp

subject = "Compliance alert: Contract 19"
body = """Hello team,
This is to inform regarding a real-time update in the contract 19:
'Data privacy protection clause is missing.'
regards,
Finance team (Vineela)
"""

resp = send_email_smtp(subject, body)
print(resp)