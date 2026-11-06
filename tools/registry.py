from typing import Dict, List, Optional, Any
from core.logger import setup_logger
from core.policy import SecurityPolicyEngine, TOOL_RISK_MAP, strip_control_args
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("ToolRegistry")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        canonical_name = SecurityPolicyEngine.normalize_tool_name(tool.name)
        self._tools[canonical_name] = tool
        # Log artik gercek uygulanan riski (TOOL_RISK_MAP) gosterir, tool'un
        # kendi beyan ettigi (bazen eski/yanlis) risk_level'i degil.
        effective_risk = TOOL_RISK_MAP.get(canonical_name, RiskLevel.HIGH)
        logger.info(f"Tool registered: '{tool.name}' -> Canonical: '{canonical_name}' (Risk: {effective_risk.value})")

    def get(self, name: str) -> Optional[BaseTool]:
        canonical_name = SecurityPolicyEngine.normalize_tool_name(name)
        return self._tools.get(canonical_name)

    def list_tools(self) -> List[Dict[str, Any]]:
        # GUVENLIK/TUTARLILIK FIX (Milestone 7): Onceden LLM'e gosterilen
        # risk_level, tool sinifinin KENDI beyanindan (bazen eski/celiskili)
        # okunuyordu. Artik gercek yetkilendirme kararini veren TEK kaynaktan
        # (TOOL_RISK_MAP) okunuyor, boylece LLM'e giden bilgi ile gercekte
        # uygulanan guvenlik karari her zaman birbiriyle tutarli olur.
        tool_list = []
        for name, tool in self._tools.items():
            effective_risk = TOOL_RISK_MAP.get(name, RiskLevel.HIGH)
            tool_list.append({
                "name": name,
                "description": tool.description,
                "risk_level": effective_risk.value,
            })
        return tool_list

    async def execute_untrusted(self, name: str, args: Optional[Dict[str, Any]] = None) -> ToolResult:
        """LLM / kullanici metninden turetilmis argumanlarla arac calistirir.

        Kontrol-duzlemi anahtarlari (bypass_approval vb.) arguman sozlugunden temizlenir;
        onay atlama bu yoldan ASLA mumkun degildir. LLM ciktisini dogrudan `execute(**args)` ile
        acmak yerine bu metot (veya strip_control_args) kullanilmalidir.
        """
        return await self.execute(name, bypass_approval=False, **strip_control_args(args or {}))

    async def execute(self, name: str, bypass_approval: bool = False, **kwargs) -> ToolResult:
        canonical_name = SecurityPolicyEngine.normalize_tool_name(name)
        tool = self.get(canonical_name)

        if not tool:
            logger.error(f"Execution failed: Tool '{name}' ({canonical_name}) not found in registry.")
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{name}' is not registered."
            )

        clean_kwargs = dict(kwargs)
        clean_kwargs.pop("bypass_approval", None)

        risk, requires_approval = SecurityPolicyEngine.evaluate_risk(canonical_name, clean_kwargs)

        if requires_approval and not bypass_approval:
            logger.warning(f"Security Gatekeeper: '{canonical_name}' requires explicit user approval!")
            return ToolResult(
                success=False,
                output=None,
                error=f"GÜVENLİK ENGELİ: '{canonical_name}' yüksek riskli bir eylemdir ve kullanıcı onayı gerektirir.",
                metadata={"error_code": "approval_required", "tool": canonical_name}
            )

        try:
            cleaned_args = tool.validate_and_clean_args(clean_kwargs)
            logger.info(f"Executing tool '{canonical_name}' with args: {cleaned_args}")
            return await tool.execute(**cleaned_args)
        except Exception as e:
            logger.error(f"Tool execution exception in '{canonical_name}': {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution exception in '{canonical_name}': {str(e)}"
            )
