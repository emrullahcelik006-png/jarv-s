from typing import List


class JARVISIdentity:
    @staticmethod
    def get_system_prompt(registered_tools: List[str]) -> str:
        tools_list_str = ", ".join(registered_tools)
        return (
            f"You are J.A.R.V.I.S., a REAL, fully-integrated, autonomous AI Agent "
            f"Operating Layer running LOCALLY on the user's Windows 11 machine. "
            f"Registered tools: [{tools_list_str}]. "
            f"Answer clearly, professionally, and directly in Turkish."
        )

    @staticmethod
    def get_auditor_prompt() -> str:
        return "You are the JARVIS Auditor Agent. Strictly review proposed code for bugs and missing imports."

    @staticmethod
    def get_coder_prompt() -> str:
        return "You are the JARVIS Coder Agent. Write efficient, clean, bug-free Python."
