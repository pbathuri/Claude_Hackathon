"""
Curated Medical Knowledge Seed Data.

This is the initial "genome" of the knowledge graph — hand-curated from
medical textbooks and WHO guidelines, focused on conditions prevalent in
the target countries (Nigeria, India, Philippines, Kenya).

The graph will self-evolve from this starting point through:
1. Scraped data enrichment (ICD-11, MedlinePlus, OpenFDA)
2. Physarum reinforcement from actual patient conversations
3. Branching leaf discovery of new symptom co-occurrences
4. Doctor feedback backpropagation

Structure:
- BODY_SYSTEMS: anatomical regions
- SYMPTOMS: observable patient complaints (~200)
- CONDITIONS: diseases/disorders (~100)
- SPECIALTIES: medical specialties (~20)
- RISK_FACTORS: predisposing factors
- MEDICATIONS: common drugs in target regions
- QUESTIONS: follow-up questions the chatbot can ask
- EDGES: symptom→condition, condition→specialty, etc.
"""

from .graph_engine import NodeType, EdgeType


# ── Body Systems ─────────────────────────────────────────────────────────────
BODY_SYSTEMS = [
    {"name": "Head and Neck", "metadata": {"regions": ["skull", "face", "throat", "neck", "ears", "eyes", "nose", "mouth"]}},
    {"name": "Chest and Respiratory", "metadata": {"regions": ["lungs", "bronchi", "trachea", "chest wall", "ribs"]}},
    {"name": "Cardiovascular", "metadata": {"regions": ["heart", "arteries", "veins", "blood"]}},
    {"name": "Abdomen and Digestive", "metadata": {"regions": ["stomach", "intestines", "liver", "gallbladder", "pancreas", "spleen"]}},
    {"name": "Musculoskeletal", "metadata": {"regions": ["bones", "joints", "muscles", "spine", "ligaments"]}},
    {"name": "Nervous System", "metadata": {"regions": ["brain", "spinal cord", "peripheral nerves"]}},
    {"name": "Skin and Integumentary", "metadata": {"regions": ["skin", "hair", "nails", "sweat glands"]}},
    {"name": "Genitourinary", "metadata": {"regions": ["kidneys", "bladder", "urethra", "reproductive organs"]}},
    {"name": "Endocrine", "metadata": {"regions": ["thyroid", "adrenals", "pituitary", "pancreas islets"]}},
    {"name": "Hematologic and Immune", "metadata": {"regions": ["blood cells", "lymph nodes", "spleen", "bone marrow"]}},
    {"name": "Mental Health", "metadata": {"regions": ["mood", "cognition", "behavior", "sleep"]}},
    {"name": "Eyes and Vision", "metadata": {"regions": ["cornea", "retina", "optic nerve", "eyelids"]}},
    {"name": "Ears and Hearing", "metadata": {"regions": ["outer ear", "middle ear", "inner ear", "eustachian tube"]}},
]


# ── Symptoms (~200 common presenting complaints) ────────────────────────────
SYMPTOMS = [
    # Head & Neurological
    {"name": "headache", "metadata": {"severity_range": "1-10", "common": True}},
    {"name": "migraine", "metadata": {"severity_range": "5-10", "with_aura": True}},
    {"name": "dizziness", "metadata": {"severity_range": "1-8"}},
    {"name": "vertigo", "metadata": {"spinning": True}},
    {"name": "fainting", "metadata": {"aka": "syncope"}},
    {"name": "confusion", "metadata": {"aka": "altered mental status"}},
    {"name": "memory loss", "metadata": {}},
    {"name": "seizure", "metadata": {"emergency": True}},
    {"name": "numbness", "metadata": {"pattern": "dermatomal or peripheral"}},
    {"name": "tingling", "metadata": {"aka": "paresthesia"}},
    {"name": "weakness", "metadata": {"focal_vs_generalized": True}},
    {"name": "tremor", "metadata": {}},
    {"name": "slurred speech", "metadata": {"emergency": True, "stroke_sign": True}},
    {"name": "vision changes", "metadata": {"types": ["blurry", "double", "loss"]}},
    {"name": "hearing loss", "metadata": {}},
    {"name": "tinnitus", "metadata": {"aka": "ringing in ears"}},

    # Respiratory
    {"name": "cough", "metadata": {"types": ["dry", "productive", "bloody"]}},
    {"name": "shortness of breath", "metadata": {"aka": "dyspnea", "emergency": True}},
    {"name": "wheezing", "metadata": {}},
    {"name": "chest tightness", "metadata": {"emergency_if_cardiac": True}},
    {"name": "sore throat", "metadata": {"common": True}},
    {"name": "runny nose", "metadata": {"aka": "rhinorrhea"}},
    {"name": "nasal congestion", "metadata": {}},
    {"name": "sneezing", "metadata": {}},
    {"name": "difficulty breathing", "metadata": {"emergency": True}},
    {"name": "coughing blood", "metadata": {"aka": "hemoptysis", "red_flag": True}},

    # Cardiovascular
    {"name": "chest pain", "metadata": {"emergency": True, "types": ["sharp", "pressure", "burning"]}},
    {"name": "palpitations", "metadata": {"aka": "heart racing"}},
    {"name": "swollen legs", "metadata": {"aka": "peripheral edema"}},
    {"name": "high blood pressure", "metadata": {"aka": "hypertension"}},
    {"name": "low blood pressure", "metadata": {"symptoms": ["dizzy", "faint"]}},
    {"name": "irregular heartbeat", "metadata": {"aka": "arrhythmia"}},

    # Gastrointestinal
    {"name": "abdominal pain", "metadata": {"locations": ["upper", "lower", "left", "right", "diffuse"]}},
    {"name": "nausea", "metadata": {"common": True}},
    {"name": "vomiting", "metadata": {"types": ["food", "bile", "blood"]}},
    {"name": "diarrhea", "metadata": {"types": ["watery", "bloody", "mucoid"]}},
    {"name": "constipation", "metadata": {}},
    {"name": "bloating", "metadata": {}},
    {"name": "heartburn", "metadata": {"aka": "acid reflux"}},
    {"name": "difficulty swallowing", "metadata": {"aka": "dysphagia"}},
    {"name": "loss of appetite", "metadata": {"aka": "anorexia"}},
    {"name": "blood in stool", "metadata": {"red_flag": True}},
    {"name": "jaundice", "metadata": {"aka": "yellowing skin/eyes", "red_flag": True}},
    {"name": "rectal bleeding", "metadata": {"red_flag": True}},

    # Musculoskeletal
    {"name": "back pain", "metadata": {"locations": ["upper", "lower", "mid"], "common": True}},
    {"name": "neck pain", "metadata": {}},
    {"name": "joint pain", "metadata": {"aka": "arthralgia"}},
    {"name": "muscle pain", "metadata": {"aka": "myalgia"}},
    {"name": "joint swelling", "metadata": {}},
    {"name": "stiffness", "metadata": {"morning_vs_constant": True}},
    {"name": "limited mobility", "metadata": {}},
    {"name": "bone pain", "metadata": {"deep": True}},

    # Skin
    {"name": "rash", "metadata": {"types": ["macular", "papular", "vesicular", "urticarial"]}},
    {"name": "itching", "metadata": {"aka": "pruritus"}},
    {"name": "skin lesion", "metadata": {}},
    {"name": "wound that won't heal", "metadata": {"red_flag": True}},
    {"name": "bruising easily", "metadata": {}},
    {"name": "skin discoloration", "metadata": {}},
    {"name": "hair loss", "metadata": {"aka": "alopecia"}},
    {"name": "excessive sweating", "metadata": {"aka": "hyperhidrosis"}},
    {"name": "dry skin", "metadata": {}},
    {"name": "swelling", "metadata": {"locations": ["face", "limbs", "generalized"]}},

    # Genitourinary
    {"name": "painful urination", "metadata": {"aka": "dysuria"}},
    {"name": "frequent urination", "metadata": {"aka": "polyuria"}},
    {"name": "blood in urine", "metadata": {"aka": "hematuria", "red_flag": True}},
    {"name": "urinary incontinence", "metadata": {}},
    {"name": "flank pain", "metadata": {"kidney_related": True}},
    {"name": "pelvic pain", "metadata": {}},
    {"name": "vaginal bleeding", "metadata": {"types": ["irregular", "postmenopausal"]}},
    {"name": "vaginal discharge", "metadata": {}},
    {"name": "testicular pain", "metadata": {"emergency_if_torsion": True}},
    {"name": "erectile dysfunction", "metadata": {}},

    # Systemic / Constitutional
    {"name": "fever", "metadata": {"common": True, "thresholds": {"low": 37.5, "high": 39.0, "very_high": 40.0}}},
    {"name": "chills", "metadata": {"often_with_fever": True}},
    {"name": "fatigue", "metadata": {"common": True, "duration_matters": True}},
    {"name": "weight loss", "metadata": {"red_flag_if_unintentional": True}},
    {"name": "weight gain", "metadata": {}},
    {"name": "night sweats", "metadata": {"red_flag": True}},
    {"name": "loss of consciousness", "metadata": {"emergency": True}},
    {"name": "dehydration", "metadata": {"signs": ["dry mouth", "decreased urine", "sunken eyes"]}},
    {"name": "malaise", "metadata": {"aka": "general feeling of unwellness"}},
    {"name": "body aches", "metadata": {"generalized": True}},
    {"name": "swollen lymph nodes", "metadata": {"aka": "lymphadenopathy"}},
    {"name": "excessive thirst", "metadata": {"aka": "polydipsia"}},

    # Mental Health
    {"name": "anxiety", "metadata": {"types": ["generalized", "panic", "social"]}},
    {"name": "depression", "metadata": {"symptoms": ["sadness", "hopelessness", "anhedonia"]}},
    {"name": "insomnia", "metadata": {"types": ["onset", "maintenance", "early waking"]}},
    {"name": "suicidal thoughts", "metadata": {"emergency": True, "crisis": True}},
    {"name": "hallucinations", "metadata": {"types": ["auditory", "visual"]}},
    {"name": "mood swings", "metadata": {}},
    {"name": "panic attacks", "metadata": {"symptoms": ["racing heart", "sweating", "trembling"]}},
    {"name": "difficulty concentrating", "metadata": {}},

    # Pediatric / Maternal
    {"name": "failure to thrive", "metadata": {"pediatric": True}},
    {"name": "delayed milestones", "metadata": {"pediatric": True}},
    {"name": "excessive crying", "metadata": {"pediatric": True}},

    # Eyes
    {"name": "eye pain", "metadata": {}},
    {"name": "red eye", "metadata": {}},
    {"name": "eye discharge", "metadata": {}},
    {"name": "blurred vision", "metadata": {}},
    {"name": "light sensitivity", "metadata": {"aka": "photophobia"}},

    # Ears
    {"name": "ear pain", "metadata": {"aka": "otalgia"}},
    {"name": "ear discharge", "metadata": {}},

    # Throat / Mouth
    {"name": "mouth sores", "metadata": {}},
    {"name": "difficulty speaking", "metadata": {}},
    {"name": "throat swelling", "metadata": {"emergency": True}},
    {"name": "hoarseness", "metadata": {}},
]


# ── Conditions (~100 diseases/disorders) ─────────────────────────────────────
# Weighted toward tropical + low-resource conditions
CONDITIONS = [
    # Infectious — Tropical (high priority for target countries)
    {"name": "Malaria", "metadata": {"tropical": True, "vector": "mosquito"}, "icd11_code": "1F40"},
    {"name": "Dengue Fever", "metadata": {"tropical": True, "vector": "mosquito"}, "icd11_code": "1D20"},
    {"name": "Typhoid Fever", "metadata": {"tropical": True, "waterborne": True}, "icd11_code": "1A07"},
    {"name": "Cholera", "metadata": {"tropical": True, "waterborne": True, "emergency": True}, "icd11_code": "1A00"},
    {"name": "Tuberculosis", "metadata": {"airborne": True, "chronic": True}, "icd11_code": "1B10"},
    {"name": "HIV/AIDS", "metadata": {"chronic": True, "bloodborne": True}, "icd11_code": "1C60"},
    {"name": "Hepatitis B", "metadata": {"chronic": True, "bloodborne": True}, "icd11_code": "1E50.1"},
    {"name": "Hepatitis A", "metadata": {"waterborne": True}, "icd11_code": "1E50.0"},
    {"name": "Leptospirosis", "metadata": {"tropical": True}, "icd11_code": "1B90"},
    {"name": "Schistosomiasis", "metadata": {"tropical": True, "parasitic": True}, "icd11_code": "1F80"},
    {"name": "Filariasis", "metadata": {"tropical": True, "parasitic": True}, "icd11_code": "1F66"},

    # Infectious — Common
    {"name": "Pneumonia", "metadata": {"respiratory": True}, "icd11_code": "CA40"},
    {"name": "Influenza", "metadata": {"respiratory": True, "seasonal": True}, "icd11_code": "1E30"},
    {"name": "COVID-19", "metadata": {"respiratory": True, "pandemic": True}, "icd11_code": "RA01"},
    {"name": "Urinary Tract Infection", "metadata": {"common": True}, "icd11_code": "GC08"},
    {"name": "Gastroenteritis", "metadata": {"common": True}, "icd11_code": "DA63"},
    {"name": "Meningitis", "metadata": {"emergency": True}, "icd11_code": "1D00"},
    {"name": "Cellulitis", "metadata": {"skin": True}, "icd11_code": "1B75"},
    {"name": "Conjunctivitis", "metadata": {"eye": True, "common": True}, "icd11_code": "9A60"},
    {"name": "Otitis Media", "metadata": {"ear": True, "common": True, "pediatric_common": True}, "icd11_code": "AB10"},
    {"name": "Pharyngitis", "metadata": {"throat": True, "common": True}, "icd11_code": "CA02"},
    {"name": "Sexually Transmitted Infection", "metadata": {"various": True}, "icd11_code": "1A60"},
    {"name": "Sepsis", "metadata": {"emergency": True, "life_threatening": True}, "icd11_code": "1G40"},

    # Non-Communicable — Cardiovascular
    {"name": "Hypertension", "metadata": {"chronic": True, "prevalence": "high"}, "icd11_code": "BA00"},
    {"name": "Heart Failure", "metadata": {"chronic": True}, "icd11_code": "BD10"},
    {"name": "Coronary Artery Disease", "metadata": {"chronic": True}, "icd11_code": "BA80"},
    {"name": "Stroke", "metadata": {"emergency": True}, "icd11_code": "8B20"},
    {"name": "Atrial Fibrillation", "metadata": {"chronic": True}, "icd11_code": "BC80"},
    {"name": "Deep Vein Thrombosis", "metadata": {"vascular": True}, "icd11_code": "BD40"},
    {"name": "Peripheral Artery Disease", "metadata": {"chronic": True}, "icd11_code": "BD30"},
    {"name": "Rheumatic Heart Disease", "metadata": {"post_infectious": True, "tropical_burden": True}, "icd11_code": "BB40"},

    # Non-Communicable — Endocrine/Metabolic
    {"name": "Type 2 Diabetes", "metadata": {"chronic": True, "prevalence": "high"}, "icd11_code": "5A11"},
    {"name": "Type 1 Diabetes", "metadata": {"chronic": True, "autoimmune": True}, "icd11_code": "5A10"},
    {"name": "Hypothyroidism", "metadata": {"chronic": True}, "icd11_code": "5A00"},
    {"name": "Hyperthyroidism", "metadata": {"chronic": True}, "icd11_code": "5A01"},
    {"name": "Anemia", "metadata": {"common": True, "types": ["iron_deficiency", "sickle_cell", "b12"]}, "icd11_code": "3A00"},
    {"name": "Sickle Cell Disease", "metadata": {"genetic": True, "africa_prevalent": True}, "icd11_code": "3A51"},
    {"name": "Malnutrition", "metadata": {"pediatric_common": True}, "icd11_code": "5B50"},

    # Non-Communicable — Respiratory
    {"name": "Asthma", "metadata": {"chronic": True, "common": True}, "icd11_code": "CA23"},
    {"name": "COPD", "metadata": {"chronic": True}, "icd11_code": "CA22"},
    {"name": "Bronchitis", "metadata": {"common": True}, "icd11_code": "CA20"},

    # Non-Communicable — GI
    {"name": "Peptic Ulcer Disease", "metadata": {"chronic": True}, "icd11_code": "DA42"},
    {"name": "Gastritis", "metadata": {"common": True}, "icd11_code": "DA41"},
    {"name": "Appendicitis", "metadata": {"surgical": True, "emergency": True}, "icd11_code": "DB10"},
    {"name": "Irritable Bowel Syndrome", "metadata": {"chronic": True, "functional": True}, "icd11_code": "DD91"},
    {"name": "Gallstones", "metadata": {"surgical": True}, "icd11_code": "DC11"},
    {"name": "Liver Cirrhosis", "metadata": {"chronic": True}, "icd11_code": "DB93"},

    # Non-Communicable — Musculoskeletal
    {"name": "Osteoarthritis", "metadata": {"chronic": True, "degenerative": True}, "icd11_code": "FA00"},
    {"name": "Rheumatoid Arthritis", "metadata": {"chronic": True, "autoimmune": True}, "icd11_code": "FA20"},
    {"name": "Gout", "metadata": {"metabolic": True}, "icd11_code": "FA25"},
    {"name": "Herniated Disc", "metadata": {"spinal": True}, "icd11_code": "FA80"},
    {"name": "Fracture", "metadata": {"traumatic": True}, "icd11_code": "NA00"},

    # Non-Communicable — Neurological
    {"name": "Epilepsy", "metadata": {"chronic": True}, "icd11_code": "8A60"},
    {"name": "Migraine Disorder", "metadata": {"chronic": True, "common": True}, "icd11_code": "8A80"},
    {"name": "Tension Headache", "metadata": {"common": True, "benign": True}, "icd11_code": "8A81"},
    {"name": "Peripheral Neuropathy", "metadata": {"chronic": True}, "icd11_code": "8C00"},

    # Non-Communicable — Mental Health
    {"name": "Major Depressive Disorder", "metadata": {"common": True}, "icd11_code": "6A70"},
    {"name": "Generalized Anxiety Disorder", "metadata": {"common": True}, "icd11_code": "6B00"},
    {"name": "Post-Traumatic Stress Disorder", "metadata": {}, "icd11_code": "6B40"},
    {"name": "Bipolar Disorder", "metadata": {"chronic": True}, "icd11_code": "6A60"},
    {"name": "Schizophrenia", "metadata": {"chronic": True}, "icd11_code": "6A20"},
    {"name": "Substance Use Disorder", "metadata": {}, "icd11_code": "6C40"},

    # Dermatological
    {"name": "Eczema", "metadata": {"chronic": True, "common": True}, "icd11_code": "EA80"},
    {"name": "Psoriasis", "metadata": {"chronic": True, "autoimmune": True}, "icd11_code": "EA90"},
    {"name": "Fungal Skin Infection", "metadata": {"common": True, "tropical_common": True}, "icd11_code": "1F28"},
    {"name": "Scabies", "metadata": {"parasitic": True, "tropical_common": True}, "icd11_code": "1G04"},

    # Maternal
    {"name": "Pre-eclampsia", "metadata": {"maternal": True, "emergency": True}, "icd11_code": "JA24"},
    {"name": "Gestational Diabetes", "metadata": {"maternal": True}, "icd11_code": "JA63"},
    {"name": "Postpartum Hemorrhage", "metadata": {"maternal": True, "emergency": True}, "icd11_code": "JB40"},
    {"name": "Ectopic Pregnancy", "metadata": {"emergency": True}, "icd11_code": "JA01"},

    # Renal
    {"name": "Kidney Stones", "metadata": {"acute": True}, "icd11_code": "GB70"},
    {"name": "Chronic Kidney Disease", "metadata": {"chronic": True}, "icd11_code": "GB60"},
    {"name": "Acute Kidney Injury", "metadata": {"emergency": True}, "icd11_code": "GB50"},

    # Cancer (common in target regions)
    {"name": "Cervical Cancer", "metadata": {"preventable": True, "hpv": True}, "icd11_code": "2C77"},
    {"name": "Breast Cancer", "metadata": {}, "icd11_code": "2C60"},
    {"name": "Prostate Cancer", "metadata": {}, "icd11_code": "2C82"},
    {"name": "Colorectal Cancer", "metadata": {}, "icd11_code": "2B90"},

    # Allergic
    {"name": "Allergic Rhinitis", "metadata": {"common": True, "seasonal": True}, "icd11_code": "CA08"},
    {"name": "Anaphylaxis", "metadata": {"emergency": True, "life_threatening": True}, "icd11_code": "4A80"},
    {"name": "Drug Allergy", "metadata": {}, "icd11_code": "4A84"},
]


# ── Medical Specialties ──────────────────────────────────────────────────────
SPECIALTIES = [
    {"name": "General Practice", "metadata": {"aka": "Family Medicine", "primary_care": True}},
    {"name": "Internal Medicine", "metadata": {"adult_medicine": True}},
    {"name": "Pediatrics", "metadata": {"children": True}},
    {"name": "Emergency Medicine", "metadata": {"acute": True}},
    {"name": "Cardiology", "metadata": {"heart": True}},
    {"name": "Pulmonology", "metadata": {"lungs": True}},
    {"name": "Gastroenterology", "metadata": {"digestive": True}},
    {"name": "Neurology", "metadata": {"brain_nerves": True}},
    {"name": "Orthopedics", "metadata": {"bones_joints": True}},
    {"name": "Dermatology", "metadata": {"skin": True}},
    {"name": "Psychiatry", "metadata": {"mental_health": True}},
    {"name": "Obstetrics and Gynecology", "metadata": {"maternal": True}},
    {"name": "Urology", "metadata": {"urinary": True}},
    {"name": "Nephrology", "metadata": {"kidney": True}},
    {"name": "Endocrinology", "metadata": {"hormones": True}},
    {"name": "Infectious Disease", "metadata": {"infections": True}},
    {"name": "Oncology", "metadata": {"cancer": True}},
    {"name": "Ophthalmology", "metadata": {"eyes": True}},
    {"name": "ENT", "metadata": {"aka": "Otolaryngology", "ear_nose_throat": True}},
    {"name": "Hematology", "metadata": {"blood": True}},
    {"name": "Rheumatology", "metadata": {"autoimmune_joints": True}},
    {"name": "Surgery", "metadata": {"surgical": True}},
]


# ── Risk Factors ─────────────────────────────────────────────────────────────
RISK_FACTORS = [
    {"name": "Smoking", "metadata": {"modifiable": True}},
    {"name": "Alcohol Use", "metadata": {"modifiable": True}},
    {"name": "Obesity", "metadata": {"modifiable": True}},
    {"name": "Sedentary Lifestyle", "metadata": {"modifiable": True}},
    {"name": "Poor Sanitation", "metadata": {"environmental": True, "tropical_risk": True}},
    {"name": "Contaminated Water", "metadata": {"environmental": True, "tropical_risk": True}},
    {"name": "Mosquito Exposure", "metadata": {"environmental": True, "tropical_risk": True}},
    {"name": "Overcrowding", "metadata": {"environmental": True}},
    {"name": "Malnutrition Risk", "metadata": {"nutritional": True}},
    {"name": "Unprotected Sex", "metadata": {"behavioral": True}},
    {"name": "Family History Cardiovascular", "metadata": {"genetic": True}},
    {"name": "Family History Diabetes", "metadata": {"genetic": True}},
    {"name": "Family History Cancer", "metadata": {"genetic": True}},
    {"name": "Age Over 50", "metadata": {"demographic": True}},
    {"name": "Age Under 5", "metadata": {"demographic": True, "pediatric": True}},
    {"name": "Pregnancy", "metadata": {"physiological": True}},
    {"name": "Immunocompromised", "metadata": {"medical": True}},
    {"name": "Previous Surgery", "metadata": {"medical": True}},
]


# ── Common Medications (target countries) ────────────────────────────────────
MEDICATIONS = [
    {"name": "Paracetamol", "metadata": {"class": "analgesic", "otc": True}},
    {"name": "Ibuprofen", "metadata": {"class": "NSAID", "otc": True}},
    {"name": "Amoxicillin", "metadata": {"class": "antibiotic", "penicillin": True}},
    {"name": "Metronidazole", "metadata": {"class": "antibiotic", "antiparasitic": True}},
    {"name": "Ciprofloxacin", "metadata": {"class": "fluoroquinolone"}},
    {"name": "Artemether-Lumefantrine", "metadata": {"class": "antimalarial", "first_line": True}},
    {"name": "Artesunate", "metadata": {"class": "antimalarial", "severe_malaria": True}},
    {"name": "Oral Rehydration Salts", "metadata": {"class": "rehydration", "essential": True}},
    {"name": "Metformin", "metadata": {"class": "antidiabetic"}},
    {"name": "Amlodipine", "metadata": {"class": "antihypertensive", "calcium_channel_blocker": True}},
    {"name": "Lisinopril", "metadata": {"class": "ACE_inhibitor"}},
    {"name": "Omeprazole", "metadata": {"class": "PPI", "acid_reducer": True}},
    {"name": "Salbutamol", "metadata": {"class": "bronchodilator", "inhaler": True}},
    {"name": "Prednisolone", "metadata": {"class": "corticosteroid"}},
    {"name": "Cotrimoxazole", "metadata": {"class": "antibiotic", "prophylaxis": True}},
    {"name": "Iron Supplements", "metadata": {"class": "supplement", "for_anemia": True}},
    {"name": "Folic Acid", "metadata": {"class": "supplement", "maternal": True}},
    {"name": "Antiretrovirals", "metadata": {"class": "ART", "for_hiv": True}},
    {"name": "Isoniazid", "metadata": {"class": "anti_tb"}},
    {"name": "Rifampicin", "metadata": {"class": "anti_tb"}},
]


# ── Follow-up Questions ──────────────────────────────────────────────────────
QUESTIONS = [
    {"name": "When did the symptoms start?", "metadata": {"reveals": "duration", "priority": 1}},
    {"name": "How severe is the pain on a scale of 1 to 10?", "metadata": {"reveals": "severity", "priority": 1}},
    {"name": "Is the pain constant or does it come and go?", "metadata": {"reveals": "pattern", "priority": 2}},
    {"name": "Does anything make it better or worse?", "metadata": {"reveals": "aggravating_relieving", "priority": 2}},
    {"name": "Have you had a fever?", "metadata": {"reveals": "fever", "priority": 1}},
    {"name": "Have you traveled recently?", "metadata": {"reveals": "travel_history", "tropical_relevant": True, "priority": 2}},
    {"name": "Are you taking any medications?", "metadata": {"reveals": "medications", "priority": 1}},
    {"name": "Do you have any allergies?", "metadata": {"reveals": "allergies", "priority": 1}},
    {"name": "Do you have any chronic conditions?", "metadata": {"reveals": "medical_history", "priority": 1}},
    {"name": "Has anyone in your family had similar symptoms?", "metadata": {"reveals": "family_history", "priority": 3}},
    {"name": "Have you lost weight recently without trying?", "metadata": {"reveals": "weight_loss", "red_flag": True, "priority": 2}},
    {"name": "Are you pregnant or could you be pregnant?", "metadata": {"reveals": "pregnancy", "priority": 1}},
    {"name": "Do you have access to clean drinking water?", "metadata": {"reveals": "sanitation", "tropical_relevant": True, "priority": 3}},
    {"name": "Have you been in contact with anyone who is sick?", "metadata": {"reveals": "exposure", "priority": 2}},
    {"name": "Do you smoke or drink alcohol?", "metadata": {"reveals": "habits", "priority": 2}},
    {"name": "Where exactly is the pain located?", "metadata": {"reveals": "location", "priority": 1}},
    {"name": "Does the pain spread to other areas?", "metadata": {"reveals": "radiation", "priority": 2}},
    {"name": "Have you noticed any blood in your stool or urine?", "metadata": {"reveals": "bleeding", "red_flag": True, "priority": 2}},
    {"name": "Have you experienced any night sweats?", "metadata": {"reveals": "night_sweats", "red_flag": True, "priority": 2}},
    {"name": "How is your appetite?", "metadata": {"reveals": "appetite", "priority": 3}},
    {"name": "Are you able to keep food and water down?", "metadata": {"reveals": "hydration_status", "priority": 1}},
    {"name": "Have you had any recent injuries?", "metadata": {"reveals": "trauma", "priority": 2}},
    {"name": "Does the symptom interfere with your daily activities?", "metadata": {"reveals": "functional_impact", "priority": 2}},
    {"name": "Have you been bitten by any insects recently?", "metadata": {"reveals": "vector_exposure", "tropical_relevant": True, "priority": 2}},
]


# ── Symptom → Condition Edges ────────────────────────────────────────────────
# Each entry: (symptom_name, condition_name, weight, confidence)
SYMPTOM_CONDITION_EDGES = [
    # Malaria
    ("fever", "Malaria", 0.8, 0.85),
    ("chills", "Malaria", 0.7, 0.80),
    ("headache", "Malaria", 0.5, 0.70),
    ("body aches", "Malaria", 0.4, 0.65),
    ("nausea", "Malaria", 0.3, 0.60),
    ("vomiting", "Malaria", 0.3, 0.55),
    ("fatigue", "Malaria", 0.4, 0.60),
    ("excessive sweating", "Malaria", 0.5, 0.70),

    # Dengue
    ("fever", "Dengue Fever", 0.8, 0.85),
    ("headache", "Dengue Fever", 0.6, 0.75),
    ("joint pain", "Dengue Fever", 0.7, 0.80),
    ("rash", "Dengue Fever", 0.6, 0.75),
    ("muscle pain", "Dengue Fever", 0.6, 0.75),
    ("body aches", "Dengue Fever", 0.5, 0.70),

    # Typhoid
    ("fever", "Typhoid Fever", 0.9, 0.85),
    ("headache", "Typhoid Fever", 0.5, 0.70),
    ("abdominal pain", "Typhoid Fever", 0.6, 0.75),
    ("diarrhea", "Typhoid Fever", 0.5, 0.70),
    ("constipation", "Typhoid Fever", 0.4, 0.60),
    ("loss of appetite", "Typhoid Fever", 0.5, 0.65),

    # Pneumonia
    ("cough", "Pneumonia", 0.8, 0.85),
    ("fever", "Pneumonia", 0.7, 0.80),
    ("shortness of breath", "Pneumonia", 0.7, 0.80),
    ("chest pain", "Pneumonia", 0.5, 0.70),
    ("fatigue", "Pneumonia", 0.4, 0.60),
    ("chills", "Pneumonia", 0.5, 0.65),

    # TB
    ("cough", "Tuberculosis", 0.8, 0.85),
    ("night sweats", "Tuberculosis", 0.7, 0.80),
    ("weight loss", "Tuberculosis", 0.7, 0.80),
    ("fever", "Tuberculosis", 0.6, 0.75),
    ("fatigue", "Tuberculosis", 0.5, 0.70),
    ("coughing blood", "Tuberculosis", 0.8, 0.90),

    # Hypertension
    ("headache", "Hypertension", 0.4, 0.60),
    ("dizziness", "Hypertension", 0.4, 0.55),
    ("vision changes", "Hypertension", 0.3, 0.50),
    ("chest pain", "Hypertension", 0.3, 0.50),
    ("shortness of breath", "Hypertension", 0.3, 0.45),

    # Diabetes
    ("excessive thirst", "Type 2 Diabetes", 0.7, 0.80),
    ("frequent urination", "Type 2 Diabetes", 0.7, 0.80),
    ("fatigue", "Type 2 Diabetes", 0.4, 0.60),
    ("blurred vision", "Type 2 Diabetes", 0.4, 0.60),
    ("weight loss", "Type 2 Diabetes", 0.5, 0.65),
    ("numbness", "Type 2 Diabetes", 0.4, 0.60),
    ("wound that won't heal", "Type 2 Diabetes", 0.5, 0.70),

    # Heart Failure
    ("shortness of breath", "Heart Failure", 0.8, 0.85),
    ("swollen legs", "Heart Failure", 0.7, 0.80),
    ("fatigue", "Heart Failure", 0.5, 0.65),
    ("palpitations", "Heart Failure", 0.4, 0.60),
    ("cough", "Heart Failure", 0.3, 0.50),

    # Stroke
    ("slurred speech", "Stroke", 0.9, 0.95),
    ("weakness", "Stroke", 0.8, 0.90),
    ("numbness", "Stroke", 0.7, 0.85),
    ("vision changes", "Stroke", 0.6, 0.80),
    ("confusion", "Stroke", 0.7, 0.85),
    ("headache", "Stroke", 0.5, 0.65),

    # Asthma
    ("wheezing", "Asthma", 0.8, 0.90),
    ("shortness of breath", "Asthma", 0.7, 0.80),
    ("cough", "Asthma", 0.5, 0.70),
    ("chest tightness", "Asthma", 0.6, 0.75),

    # UTI
    ("painful urination", "Urinary Tract Infection", 0.8, 0.90),
    ("frequent urination", "Urinary Tract Infection", 0.7, 0.85),
    ("blood in urine", "Urinary Tract Infection", 0.5, 0.70),
    ("abdominal pain", "Urinary Tract Infection", 0.4, 0.60),
    ("fever", "Urinary Tract Infection", 0.3, 0.50),

    # Appendicitis
    ("abdominal pain", "Appendicitis", 0.9, 0.90),
    ("nausea", "Appendicitis", 0.6, 0.70),
    ("vomiting", "Appendicitis", 0.5, 0.65),
    ("fever", "Appendicitis", 0.5, 0.65),
    ("loss of appetite", "Appendicitis", 0.5, 0.65),

    # Gastroenteritis
    ("diarrhea", "Gastroenteritis", 0.8, 0.90),
    ("vomiting", "Gastroenteritis", 0.7, 0.85),
    ("nausea", "Gastroenteritis", 0.6, 0.75),
    ("abdominal pain", "Gastroenteritis", 0.5, 0.70),
    ("fever", "Gastroenteritis", 0.4, 0.60),
    ("dehydration", "Gastroenteritis", 0.6, 0.75),

    # Cholera
    ("diarrhea", "Cholera", 0.9, 0.95),
    ("vomiting", "Cholera", 0.7, 0.85),
    ("dehydration", "Cholera", 0.9, 0.95),

    # Meningitis
    ("headache", "Meningitis", 0.8, 0.85),
    ("fever", "Meningitis", 0.8, 0.85),
    ("neck pain", "Meningitis", 0.8, 0.90),
    ("confusion", "Meningitis", 0.6, 0.75),
    ("light sensitivity", "Meningitis", 0.7, 0.80),
    ("rash", "Meningitis", 0.5, 0.70),

    # Anemia / Sickle Cell
    ("fatigue", "Anemia", 0.7, 0.80),
    ("dizziness", "Anemia", 0.5, 0.70),
    ("weakness", "Anemia", 0.6, 0.75),
    ("shortness of breath", "Anemia", 0.4, 0.60),
    ("joint pain", "Sickle Cell Disease", 0.7, 0.80),
    ("bone pain", "Sickle Cell Disease", 0.8, 0.85),
    ("fatigue", "Sickle Cell Disease", 0.6, 0.75),

    # Depression
    ("depression", "Major Depressive Disorder", 0.9, 0.90),
    ("insomnia", "Major Depressive Disorder", 0.6, 0.75),
    ("fatigue", "Major Depressive Disorder", 0.5, 0.65),
    ("loss of appetite", "Major Depressive Disorder", 0.5, 0.65),
    ("difficulty concentrating", "Major Depressive Disorder", 0.5, 0.70),
    ("weight loss", "Major Depressive Disorder", 0.3, 0.50),
    ("suicidal thoughts", "Major Depressive Disorder", 0.8, 0.90),

    # Anxiety
    ("anxiety", "Generalized Anxiety Disorder", 0.9, 0.90),
    ("palpitations", "Generalized Anxiety Disorder", 0.5, 0.65),
    ("insomnia", "Generalized Anxiety Disorder", 0.5, 0.65),
    ("panic attacks", "Generalized Anxiety Disorder", 0.7, 0.80),
    ("tremor", "Generalized Anxiety Disorder", 0.3, 0.50),

    # Kidney Stones
    ("flank pain", "Kidney Stones", 0.8, 0.90),
    ("blood in urine", "Kidney Stones", 0.7, 0.85),
    ("nausea", "Kidney Stones", 0.4, 0.60),
    ("vomiting", "Kidney Stones", 0.4, 0.55),
    ("painful urination", "Kidney Stones", 0.5, 0.70),

    # Eczema
    ("itching", "Eczema", 0.8, 0.85),
    ("rash", "Eczema", 0.7, 0.80),
    ("dry skin", "Eczema", 0.6, 0.75),

    # Peptic Ulcer
    ("abdominal pain", "Peptic Ulcer Disease", 0.7, 0.80),
    ("heartburn", "Peptic Ulcer Disease", 0.6, 0.75),
    ("nausea", "Peptic Ulcer Disease", 0.4, 0.60),
    ("blood in stool", "Peptic Ulcer Disease", 0.5, 0.70),

    # Epilepsy
    ("seizure", "Epilepsy", 0.9, 0.95),
    ("confusion", "Epilepsy", 0.4, 0.60),
    ("loss of consciousness", "Epilepsy", 0.6, 0.75),

    # Sepsis
    ("fever", "Sepsis", 0.8, 0.85),
    ("confusion", "Sepsis", 0.6, 0.75),
    ("shortness of breath", "Sepsis", 0.5, 0.70),
    ("low blood pressure", "Sepsis", 0.7, 0.80),
    ("palpitations", "Sepsis", 0.4, 0.60),

    # Pre-eclampsia
    ("high blood pressure", "Pre-eclampsia", 0.9, 0.95),
    ("headache", "Pre-eclampsia", 0.6, 0.70),
    ("vision changes", "Pre-eclampsia", 0.7, 0.80),
    ("swelling", "Pre-eclampsia", 0.7, 0.80),
    ("abdominal pain", "Pre-eclampsia", 0.5, 0.65),

    # Cancer warning signs
    ("weight loss", "Cervical Cancer", 0.4, 0.50),
    ("vaginal bleeding", "Cervical Cancer", 0.6, 0.70),
    ("weight loss", "Colorectal Cancer", 0.4, 0.50),
    ("blood in stool", "Colorectal Cancer", 0.6, 0.70),
    ("rectal bleeding", "Colorectal Cancer", 0.7, 0.75),

    # Allergic
    ("rash", "Drug Allergy", 0.6, 0.70),
    ("swelling", "Drug Allergy", 0.5, 0.65),
    ("shortness of breath", "Anaphylaxis", 0.8, 0.90),
    ("swelling", "Anaphylaxis", 0.7, 0.85),
    ("rash", "Anaphylaxis", 0.6, 0.75),
    ("throat swelling", "Anaphylaxis", 0.9, 0.95),
    ("low blood pressure", "Anaphylaxis", 0.7, 0.80),

    # Conjunctivitis
    ("red eye", "Conjunctivitis", 0.8, 0.90),
    ("eye discharge", "Conjunctivitis", 0.7, 0.85),
    ("itching", "Conjunctivitis", 0.5, 0.65),

    # Otitis Media
    ("ear pain", "Otitis Media", 0.8, 0.90),
    ("ear discharge", "Otitis Media", 0.6, 0.75),
    ("fever", "Otitis Media", 0.4, 0.60),
    ("hearing loss", "Otitis Media", 0.4, 0.60),
]


# ── Condition → Specialty Edges ──────────────────────────────────────────────
CONDITION_SPECIALTY_EDGES = [
    # Tropical / Infectious
    ("Malaria", "Infectious Disease", 0.9, 0.95),
    ("Malaria", "General Practice", 0.7, 0.85),
    ("Dengue Fever", "Infectious Disease", 0.9, 0.95),
    ("Typhoid Fever", "Infectious Disease", 0.8, 0.90),
    ("Typhoid Fever", "General Practice", 0.6, 0.80),
    ("Cholera", "Infectious Disease", 0.9, 0.95),
    ("Cholera", "Emergency Medicine", 0.8, 0.90),
    ("Tuberculosis", "Infectious Disease", 0.9, 0.95),
    ("Tuberculosis", "Pulmonology", 0.7, 0.80),
    ("HIV/AIDS", "Infectious Disease", 0.9, 0.95),
    ("Meningitis", "Infectious Disease", 0.8, 0.90),
    ("Meningitis", "Neurology", 0.7, 0.80),
    ("Meningitis", "Emergency Medicine", 0.8, 0.85),
    ("Sepsis", "Emergency Medicine", 0.9, 0.95),
    ("Sepsis", "Infectious Disease", 0.8, 0.90),

    # Cardiovascular
    ("Hypertension", "Cardiology", 0.7, 0.85),
    ("Hypertension", "Internal Medicine", 0.6, 0.80),
    ("Hypertension", "General Practice", 0.5, 0.75),
    ("Heart Failure", "Cardiology", 0.9, 0.95),
    ("Coronary Artery Disease", "Cardiology", 0.9, 0.95),
    ("Stroke", "Neurology", 0.9, 0.95),
    ("Stroke", "Emergency Medicine", 0.9, 0.95),
    ("Atrial Fibrillation", "Cardiology", 0.9, 0.90),
    ("Rheumatic Heart Disease", "Cardiology", 0.8, 0.90),

    # Respiratory
    ("Pneumonia", "Pulmonology", 0.7, 0.85),
    ("Pneumonia", "General Practice", 0.6, 0.80),
    ("Asthma", "Pulmonology", 0.8, 0.90),
    ("COPD", "Pulmonology", 0.9, 0.90),

    # GI
    ("Gastroenteritis", "General Practice", 0.7, 0.85),
    ("Gastroenteritis", "Gastroenterology", 0.4, 0.60),
    ("Appendicitis", "Surgery", 0.9, 0.95),
    ("Peptic Ulcer Disease", "Gastroenterology", 0.8, 0.90),
    ("Gallstones", "Surgery", 0.7, 0.80),
    ("Gallstones", "Gastroenterology", 0.6, 0.75),
    ("Liver Cirrhosis", "Gastroenterology", 0.9, 0.90),
    ("Irritable Bowel Syndrome", "Gastroenterology", 0.7, 0.80),

    # Endocrine
    ("Type 2 Diabetes", "Endocrinology", 0.8, 0.90),
    ("Type 2 Diabetes", "Internal Medicine", 0.6, 0.80),
    ("Hypothyroidism", "Endocrinology", 0.8, 0.90),
    ("Hyperthyroidism", "Endocrinology", 0.8, 0.90),
    ("Gestational Diabetes", "Obstetrics and Gynecology", 0.7, 0.85),
    ("Gestational Diabetes", "Endocrinology", 0.5, 0.70),

    # Musculoskeletal
    ("Osteoarthritis", "Orthopedics", 0.7, 0.85),
    ("Osteoarthritis", "Rheumatology", 0.5, 0.70),
    ("Rheumatoid Arthritis", "Rheumatology", 0.9, 0.95),
    ("Gout", "Rheumatology", 0.7, 0.85),
    ("Herniated Disc", "Orthopedics", 0.8, 0.90),
    ("Fracture", "Orthopedics", 0.9, 0.95),
    ("Fracture", "Emergency Medicine", 0.7, 0.80),

    # Neurological
    ("Epilepsy", "Neurology", 0.9, 0.95),
    ("Migraine Disorder", "Neurology", 0.7, 0.85),
    ("Peripheral Neuropathy", "Neurology", 0.8, 0.90),

    # Mental Health
    ("Major Depressive Disorder", "Psychiatry", 0.9, 0.95),
    ("Generalized Anxiety Disorder", "Psychiatry", 0.8, 0.90),
    ("Bipolar Disorder", "Psychiatry", 0.9, 0.95),
    ("Schizophrenia", "Psychiatry", 0.9, 0.95),
    ("Post-Traumatic Stress Disorder", "Psychiatry", 0.8, 0.90),

    # Dermatological
    ("Eczema", "Dermatology", 0.8, 0.90),
    ("Psoriasis", "Dermatology", 0.9, 0.90),
    ("Fungal Skin Infection", "Dermatology", 0.7, 0.85),
    ("Scabies", "Dermatology", 0.7, 0.85),

    # Renal
    ("Kidney Stones", "Urology", 0.8, 0.90),
    ("Kidney Stones", "Nephrology", 0.5, 0.70),
    ("Chronic Kidney Disease", "Nephrology", 0.9, 0.95),
    ("Urinary Tract Infection", "Urology", 0.5, 0.70),
    ("Urinary Tract Infection", "General Practice", 0.7, 0.85),

    # Maternal
    ("Pre-eclampsia", "Obstetrics and Gynecology", 0.9, 0.95),
    ("Postpartum Hemorrhage", "Obstetrics and Gynecology", 0.9, 0.95),
    ("Ectopic Pregnancy", "Obstetrics and Gynecology", 0.9, 0.95),
    ("Ectopic Pregnancy", "Emergency Medicine", 0.8, 0.85),

    # Hematologic
    ("Anemia", "Hematology", 0.7, 0.85),
    ("Anemia", "Internal Medicine", 0.5, 0.70),
    ("Sickle Cell Disease", "Hematology", 0.9, 0.95),

    # Cancer
    ("Cervical Cancer", "Oncology", 0.9, 0.95),
    ("Cervical Cancer", "Obstetrics and Gynecology", 0.7, 0.80),
    ("Breast Cancer", "Oncology", 0.9, 0.95),
    ("Prostate Cancer", "Oncology", 0.9, 0.95),
    ("Prostate Cancer", "Urology", 0.7, 0.80),
    ("Colorectal Cancer", "Oncology", 0.9, 0.95),

    # Allergic
    ("Anaphylaxis", "Emergency Medicine", 0.9, 0.95),
    ("Drug Allergy", "Internal Medicine", 0.5, 0.65),
    ("Allergic Rhinitis", "ENT", 0.6, 0.75),

    # Eyes / Ears
    ("Conjunctivitis", "Ophthalmology", 0.7, 0.85),
    ("Conjunctivitis", "General Practice", 0.6, 0.80),
    ("Otitis Media", "ENT", 0.8, 0.90),
    ("Otitis Media", "Pediatrics", 0.5, 0.70),
]


# ── Condition → Body System Edges ────────────────────────────────────────────
CONDITION_BODY_SYSTEM_EDGES = [
    ("Malaria", "Hematologic and Immune"),
    ("Dengue Fever", "Hematologic and Immune"),
    ("Pneumonia", "Chest and Respiratory"),
    ("Tuberculosis", "Chest and Respiratory"),
    ("Hypertension", "Cardiovascular"),
    ("Heart Failure", "Cardiovascular"),
    ("Stroke", "Nervous System"),
    ("Type 2 Diabetes", "Endocrine"),
    ("Asthma", "Chest and Respiratory"),
    ("Gastroenteritis", "Abdomen and Digestive"),
    ("Appendicitis", "Abdomen and Digestive"),
    ("Peptic Ulcer Disease", "Abdomen and Digestive"),
    ("Urinary Tract Infection", "Genitourinary"),
    ("Kidney Stones", "Genitourinary"),
    ("Osteoarthritis", "Musculoskeletal"),
    ("Eczema", "Skin and Integumentary"),
    ("Major Depressive Disorder", "Mental Health"),
    ("Epilepsy", "Nervous System"),
    ("Anemia", "Hematologic and Immune"),
    ("Pre-eclampsia", "Cardiovascular"),
    ("Conjunctivitis", "Eyes and Vision"),
    ("Otitis Media", "Ears and Hearing"),
    ("Meningitis", "Nervous System"),
    ("Cholera", "Abdomen and Digestive"),
    ("Typhoid Fever", "Abdomen and Digestive"),
    ("Liver Cirrhosis", "Abdomen and Digestive"),
    ("COPD", "Chest and Respiratory"),
    ("Coronary Artery Disease", "Cardiovascular"),
    ("Chronic Kidney Disease", "Genitourinary"),
    ("Cervical Cancer", "Genitourinary"),
    ("Sickle Cell Disease", "Hematologic and Immune"),
    ("Rheumatoid Arthritis", "Musculoskeletal"),
    ("HIV/AIDS", "Hematologic and Immune"),
    ("Sepsis", "Hematologic and Immune"),
    ("Anaphylaxis", "Hematologic and Immune"),
    ("Migraine Disorder", "Head and Neck"),
    ("Tension Headache", "Head and Neck"),
]


# ── Symptom → Body System Edges ──────────────────────────────────────────────
SYMPTOM_BODY_SYSTEM_EDGES = [
    ("headache", "Head and Neck"),
    ("dizziness", "Head and Neck"),
    ("cough", "Chest and Respiratory"),
    ("shortness of breath", "Chest and Respiratory"),
    ("wheezing", "Chest and Respiratory"),
    ("chest pain", "Cardiovascular"),
    ("palpitations", "Cardiovascular"),
    ("abdominal pain", "Abdomen and Digestive"),
    ("nausea", "Abdomen and Digestive"),
    ("vomiting", "Abdomen and Digestive"),
    ("diarrhea", "Abdomen and Digestive"),
    ("back pain", "Musculoskeletal"),
    ("joint pain", "Musculoskeletal"),
    ("muscle pain", "Musculoskeletal"),
    ("rash", "Skin and Integumentary"),
    ("itching", "Skin and Integumentary"),
    ("painful urination", "Genitourinary"),
    ("blood in urine", "Genitourinary"),
    ("seizure", "Nervous System"),
    ("numbness", "Nervous System"),
    ("confusion", "Nervous System"),
    ("anxiety", "Mental Health"),
    ("depression", "Mental Health"),
    ("insomnia", "Mental Health"),
    ("eye pain", "Eyes and Vision"),
    ("red eye", "Eyes and Vision"),
    ("ear pain", "Ears and Hearing"),
    ("fever", "Hematologic and Immune"),
    ("swollen lymph nodes", "Hematologic and Immune"),
    ("sore throat", "Head and Neck"),
    ("neck pain", "Head and Neck"),
    ("flank pain", "Genitourinary"),
    ("vaginal bleeding", "Genitourinary"),
    ("pelvic pain", "Genitourinary"),
]


# ── Risk Factor → Condition Edges ────────────────────────────────────────────
RISK_CONDITION_EDGES = [
    ("Smoking", "COPD", 0.8, 0.90),
    ("Smoking", "Coronary Artery Disease", 0.6, 0.85),
    ("Smoking", "Hypertension", 0.5, 0.75),
    ("Alcohol Use", "Liver Cirrhosis", 0.7, 0.85),
    ("Obesity", "Type 2 Diabetes", 0.7, 0.85),
    ("Obesity", "Hypertension", 0.6, 0.80),
    ("Obesity", "Osteoarthritis", 0.5, 0.70),
    ("Poor Sanitation", "Cholera", 0.8, 0.90),
    ("Poor Sanitation", "Typhoid Fever", 0.7, 0.85),
    ("Contaminated Water", "Cholera", 0.9, 0.95),
    ("Contaminated Water", "Hepatitis A", 0.6, 0.80),
    ("Mosquito Exposure", "Malaria", 0.9, 0.95),
    ("Mosquito Exposure", "Dengue Fever", 0.8, 0.90),
    ("Unprotected Sex", "HIV/AIDS", 0.7, 0.85),
    ("Unprotected Sex", "Sexually Transmitted Infection", 0.8, 0.90),
    ("Family History Cardiovascular", "Coronary Artery Disease", 0.5, 0.75),
    ("Family History Diabetes", "Type 2 Diabetes", 0.5, 0.75),
    ("Pregnancy", "Pre-eclampsia", 0.3, 0.80),
    ("Pregnancy", "Gestational Diabetes", 0.2, 0.75),
    ("Immunocompromised", "Tuberculosis", 0.5, 0.80),
    ("Immunocompromised", "Pneumonia", 0.5, 0.75),
    ("Age Under 5", "Malaria", 0.4, 0.80),
    ("Age Under 5", "Gastroenteritis", 0.5, 0.80),
    ("Age Under 5", "Malnutrition", 0.4, 0.75),
    ("Age Over 50", "Hypertension", 0.5, 0.80),
    ("Age Over 50", "Type 2 Diabetes", 0.4, 0.70),
    ("Age Over 50", "Osteoarthritis", 0.5, 0.75),
    ("Malnutrition Risk", "Anemia", 0.6, 0.80),
    ("Malnutrition Risk", "Malnutrition", 0.7, 0.85),
]


# ── Condition → Medication Edges ─────────────────────────────────────────────
CONDITION_MEDICATION_EDGES = [
    ("Malaria", "Artemether-Lumefantrine", 0.9, 0.95),
    ("Malaria", "Artesunate", 0.7, 0.90),
    ("Gastroenteritis", "Oral Rehydration Salts", 0.9, 0.95),
    ("Cholera", "Oral Rehydration Salts", 0.9, 0.95),
    ("Type 2 Diabetes", "Metformin", 0.8, 0.90),
    ("Hypertension", "Amlodipine", 0.7, 0.85),
    ("Hypertension", "Lisinopril", 0.7, 0.85),
    ("Pneumonia", "Amoxicillin", 0.7, 0.85),
    ("Urinary Tract Infection", "Ciprofloxacin", 0.7, 0.80),
    ("Peptic Ulcer Disease", "Omeprazole", 0.8, 0.90),
    ("Asthma", "Salbutamol", 0.8, 0.90),
    ("Tuberculosis", "Isoniazid", 0.8, 0.90),
    ("Tuberculosis", "Rifampicin", 0.8, 0.90),
    ("HIV/AIDS", "Antiretrovirals", 0.9, 0.95),
    ("HIV/AIDS", "Cotrimoxazole", 0.6, 0.80),
    ("Anemia", "Iron Supplements", 0.8, 0.90),
    ("Osteoarthritis", "Paracetamol", 0.5, 0.70),
    ("Osteoarthritis", "Ibuprofen", 0.5, 0.70),
    ("Eczema", "Prednisolone", 0.4, 0.60),
]


# ── Symptom Co-occurrence (PRESENTS_WITH) Edges ─────────────────────────────
SYMPTOM_COOCCURRENCE_EDGES = [
    ("fever", "chills", 0.8, 0.90),
    ("fever", "body aches", 0.6, 0.80),
    ("fever", "headache", 0.5, 0.75),
    ("nausea", "vomiting", 0.7, 0.85),
    ("diarrhea", "dehydration", 0.7, 0.85),
    ("diarrhea", "abdominal pain", 0.5, 0.75),
    ("cough", "sore throat", 0.4, 0.70),
    ("cough", "fever", 0.4, 0.65),
    ("chest pain", "shortness of breath", 0.6, 0.80),
    ("headache", "nausea", 0.4, 0.65),
    ("headache", "light sensitivity", 0.5, 0.70),
    ("joint pain", "joint swelling", 0.6, 0.80),
    ("joint pain", "stiffness", 0.5, 0.75),
    ("anxiety", "insomnia", 0.5, 0.75),
    ("depression", "insomnia", 0.5, 0.75),
    ("depression", "fatigue", 0.5, 0.75),
    ("night sweats", "weight loss", 0.5, 0.70),
    ("night sweats", "fever", 0.4, 0.65),
    ("painful urination", "frequent urination", 0.6, 0.80),
    ("rash", "itching", 0.5, 0.75),
    ("swollen legs", "shortness of breath", 0.5, 0.70),
    ("excessive thirst", "frequent urination", 0.7, 0.85),
    ("slurred speech", "weakness", 0.7, 0.85),
    ("slurred speech", "confusion", 0.6, 0.80),
]


# ── Question → Symptom (what each question reveals) ─────────────────────────
QUESTION_SYMPTOM_EDGES = [
    ("When did the symptoms start?", "fatigue", 0.3, 0.50),
    ("Have you had a fever?", "fever", 0.8, 0.90),
    ("Have you had a fever?", "chills", 0.5, 0.70),
    ("Have you traveled recently?", "fever", 0.3, 0.50),
    ("Are you taking any medications?", "drug allergy symptom", 0.2, 0.40),
    ("Do you smoke or drink alcohol?", "cough", 0.3, 0.50),
    ("Have you been bitten by any insects recently?", "fever", 0.4, 0.60),
    ("Have you lost weight recently without trying?", "weight loss", 0.8, 0.90),
    ("Have you noticed any blood in your stool or urine?", "blood in stool", 0.8, 0.90),
    ("Have you noticed any blood in your stool or urine?", "blood in urine", 0.8, 0.90),
    ("Have you experienced any night sweats?", "night sweats", 0.8, 0.90),
    ("Do you have access to clean drinking water?", "diarrhea", 0.3, 0.50),
    ("Are you pregnant or could you be pregnant?", "pelvic pain", 0.3, 0.50),
    ("Where exactly is the pain located?", "abdominal pain", 0.5, 0.60),
    ("Does the pain spread to other areas?", "chest pain", 0.4, 0.55),
    ("Are you able to keep food and water down?", "vomiting", 0.7, 0.80),
    ("Are you able to keep food and water down?", "dehydration", 0.5, 0.70),
]
