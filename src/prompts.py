from langchain_core.prompts import ChatPromptTemplate


human_interaction_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a medical assistant helping to identify patient symptoms. "
                "Ask clarifying questions to gather more symptoms if needed. "
                "If a voice transcript is provided, treat it as the patient's latest "
                "spoken input and factor it into your response. "
                "Always return a user-facing message and the updated symptom list."
            ),
        ),
        (
            "human",
            (
                "Symptoms collected so far: {symptoms}\n\n"
                "Latest voice transcript (if any): {transcript}\n\n"
                "Continue the diagnostic conversation."
            ),
        ),
    ]
)


continue_gate_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are deciding whether enough symptoms have been collected "
                "to make a preliminary assessment. "
                "Reply with only 'continue' or 'end'."
            ),
        ),
        (
            "human",
            "Symptoms collected so far: {symptoms}\nMessage turns: {turns}",
        ),
    ]
)
