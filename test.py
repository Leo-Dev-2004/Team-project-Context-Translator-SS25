import json
from detector import detect_terms

# test.py ist bisschen outdated und halb sinnlos, aber kann zum verstehen helfen, zeigt auch bisschen verhalten.
# WICHTIG: test.py printed nur das rohe ergebniss, nicht was in die queue kommt oder so,
# NUR was der llm selber rausgibt, vor verarbeitung (es zeigt nicht was an den großen llm weitergeleitet wird).
# Zum ausführen, einfach "python test.py" im command prompt ausführen.

print("Professor")
terms_prof = detect_terms("The system stores passwords using a salted SHA-256 hash.", user_role="Computer Science Professor")
print(json.dumps(terms_prof, indent=2))

print("\nSchool Student")
terms_s = detect_terms("The system stores passwords using a salted SHA-256 hash.", user_role="School Student")
print(json.dumps(terms_s, indent=2))

print("\nNo Domain")
terms = detect_terms("The system stores passwords using a salted SHA-256 hash.")
print(json.dumps(terms, indent=2))

print("Law Student")
terms_law = detect_terms(
    "The contract contains a force majeure clause that voids obligations during natural disasters.",
    user_role="Undergraduate Law Student"
)
print(json.dumps(terms_law, indent=2))

print("\nMedical Professional")
terms_med = detect_terms(
    "The patient was diagnosed with atrial fibrillation and prescribed a beta-blocker.",
    user_role="Medical Doctor"
)
print(json.dumps(terms_med, indent=2))

print("\nBusiness Executive")
terms_exec = detect_terms(
    "We're leveraging EBITDA to assess financial performance before considering amortization.",
    user_role="Business Executive"
)
print(json.dumps(terms_exec, indent=2))

print("\nHigh School Student")
terms_hs = detect_terms(
    "Transformer models use attention mechanisms to weigh input sequences dynamically.",
    user_role="High School Student"
)
print(json.dumps(terms_hs, indent=2))

print("\nNo Domain")
terms_default = detect_terms(
    "Microservices architecture promotes modular development for scalable systems."
)
print(json.dumps(terms_default, indent=2))

print("\nNo Domain")
terms_default_ai = detect_terms(
    "Reinforcement learning optimizes decision-making through trial-and-error interactions."
)
print(json.dumps(terms_default_ai, indent=2))

print("\nNo Domain")
terms_default_security = detect_terms(
    "Zero trust architecture assumes no implicit trust between network segments."
)
print(json.dumps(terms_default_security, indent=2))

print("\nNo Domain")
terms_default_network = detect_terms(
    "The router supports IPv6 and uses NAT to manage local addressing."
)
print(json.dumps(terms_default_network, indent=2))
