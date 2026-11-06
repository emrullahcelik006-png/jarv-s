from typing import List, Optional
from core.logger import setup_logger
from core.types import ChatResponse
from skills.base import (
    BaseSkill,
    SkillContext,
    ScreenAnalysisSkill,
    ProblemReportSkill,
    ContextReferenceSkill,
    SingleActionSkill,
    GeneralChatSkill
)
from skills.god_mode import GodModeSkill

logger = setup_logger("SkillRegistry")


class SkillRegistry:
    def __init__(self):
        self.skills: List[BaseSkill] = []
        self._register_default_skills()

    def _register_default_skills(self):
        # Milestone 15: GOD MODE en yuksek oncelik (liste basinda + score 1.0)
        self.register(GodModeSkill())
        self.register(ScreenAnalysisSkill())
        self.register(ProblemReportSkill())
        self.register(ContextReferenceSkill())
        self.register(SingleActionSkill())
        self.register(GeneralChatSkill())

    def register(self, skill: BaseSkill):
        self.skills.append(skill)

    async def execute_best_skill(self, context: SkillContext) -> ChatResponse:
        best_skill: Optional[BaseSkill] = None
        highest_score = -1.0

        for skill in self.skills:
            try:
                score = await skill.can_handle(context)
                if score > highest_score:
                    highest_score = score
                    best_skill = skill
            except Exception as e:
                logger.warning(f"Error evaluating skill '{getattr(skill, 'name', 'unknown')}': {e}")

        if not best_skill or highest_score <= 0.0:
            best_skill = GeneralChatSkill()

        skill_name = getattr(best_skill, "name", "general_chat")
        logger.info(f"Executing best skill '{skill_name}' (Score: {highest_score:.2f})")

        try:
            return await best_skill.execute(context)
        except Exception as exec_err:
            logger.error(f"Skill execution exception in '{skill_name}': {exec_err}")
            return ChatResponse(
                response=f"⚠️ **[İŞLEM BİLDİRİMİ]**: Eylem gerçekleştirilirken bir sorun oluştu: {str(exec_err)}",
                session_id=context.request.session_id,
                matched_tool=None
            )
