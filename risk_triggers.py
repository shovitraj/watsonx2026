"""
Risk trigger keywords for Discovery PoC Orchestrator.

This module defines keyword patterns that flag specific risks or compliance requirements
when detected in meeting notes. Each trigger maps to a risk category that may require
additional scrutiny, mitigation planning, or specialized expertise.
"""

# Keyword → Risk Flag mapping
# Keys are lowercase keywords/phrases to search for in meeting notes
# Values are risk categories that get flagged when keywords are detected

RISK_TRIGGERS = {
    # Healthcare & Compliance
    "hipaa": "HIPAA Compliance",
    "phi": "HIPAA Compliance",
    "protected health information": "HIPAA Compliance",
    "patient data": "HIPAA Compliance",
    "medical records": "HIPAA Compliance",
    "healthcare": "HIPAA Compliance",
    
    # Privacy & Data Protection
    "gdpr": "GDPR Compliance",
    "general data protection regulation": "GDPR Compliance",
    "data privacy": "GDPR Compliance",
    "personal data": "GDPR Compliance",
    "pii": "PII Protection",
    "personally identifiable information": "PII Protection",
    "data residency": "Data Residency",
    "data sovereignty": "Data Residency",
    
    # Enterprise Systems
    "sap": "SAP Integration",
    "s/4hana": "SAP Integration",
    "sap hana": "SAP Integration",
    "salesforce": "CRM Integration",
    "oracle": "Enterprise System Integration",
    "peoplesoft": "Enterprise System Integration",
    "workday": "Enterprise System Integration",
    
    # Voice & Conversational AI
    "voice": "Voice/Audio Processing",
    "speech": "Voice/Audio Processing",
    "audio": "Voice/Audio Processing",
    "call center": "Voice/Audio Processing",
    "ivr": "Voice/Audio Processing",
    "telephony": "Voice/Audio Processing",
    "conversational ai": "Voice/Audio Processing",
    
    # Infrastructure & Deployment
    "on-premise": "On-Premises Deployment",
    "on-prem": "On-Premises Deployment",
    "on premise": "On-Premises Deployment",
    "air-gapped": "Air-Gapped Environment",
    "air gapped": "Air-Gapped Environment",
    "disconnected": "Air-Gapped Environment",
    "private cloud": "Private Cloud",
    "hybrid cloud": "Hybrid Cloud",
    
    # Authentication & Identity
    "sso": "SSO/Identity Integration",
    "single sign-on": "SSO/Identity Integration",
    "azure ad": "SSO/Identity Integration",
    "azure active directory": "SSO/Identity Integration",
    "active directory": "SSO/Identity Integration",
    "okta": "SSO/Identity Integration",
    "saml": "SSO/Identity Integration",
    "ldap": "SSO/Identity Integration",
    "oauth": "SSO/Identity Integration",
    
    # Security & Compliance
    "sox": "SOX Compliance",
    "sarbanes-oxley": "SOX Compliance",
    "pci": "PCI Compliance",
    "pci-dss": "PCI Compliance",
    "fedramp": "FedRAMP Compliance",
    "iso 27001": "ISO 27001 Compliance",
    "nist": "NIST Compliance",
    "fisma": "FISMA Compliance",
    
    # Data & AI Specific
    "model training": "Custom Model Training",
    "fine-tuning": "Custom Model Training",
    "fine tuning": "Custom Model Training",
    "rag": "RAG Implementation",
    "retrieval augmented generation": "RAG Implementation",
    "vector database": "Vector Database",
    "embedding": "Embedding/Vector Search",
    "real-time": "Real-Time Processing",
    "streaming": "Real-Time Processing",
    "batch processing": "Batch Processing",
}


def detect_risks(text: str) -> dict[str, list[str]]:
    """
    Scan text for risk trigger keywords and return detected risk categories.
    
    Args:
        text: Meeting notes or other text to scan
        
    Returns:
        Dictionary mapping risk categories to lists of matched keywords
        Example: {"HIPAA Compliance": ["hipaa", "patient data"], "SAP Integration": ["sap"]}
    """
    text_lower = text.lower()
    detected = {}
    
    for keyword, risk_category in RISK_TRIGGERS.items():
        if keyword in text_lower:
            if risk_category not in detected:
                detected[risk_category] = []
            detected[risk_category].append(keyword)
    
    return detected


def get_risk_severity(risk_category: str) -> str:
    """
    Assign default severity level to risk categories.
    
    Args:
        risk_category: Risk category name
        
    Returns:
        Severity level: "High", "Medium", or "Low"
    """
    high_severity = {
        "HIPAA Compliance",
        "GDPR Compliance",
        "PII Protection",
        "Air-Gapped Environment",
        "SOX Compliance",
        "PCI Compliance",
        "FedRAMP Compliance",
    }
    
    medium_severity = {
        "SAP Integration",
        "On-Premises Deployment",
        "SSO/Identity Integration",
        "Data Residency",
        "Custom Model Training",
        "Real-Time Processing",
    }
    
    if risk_category in high_severity:
        return "High"
    elif risk_category in medium_severity:
        return "Medium"
    else:
        return "Low"
