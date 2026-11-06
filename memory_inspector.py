from typing import Optional
from core.logger import setup_logger
from core.types import RiskLevel
from memory.service import MemoryService
from tools.base import BaseTool, ToolResult

logger = setup_logger("MemoryInspectorTool")


class MemoryInspectorTool(BaseTool):
    name = "memory_inspector"
    description = "Inspects, updates, or deletes stored user facts and memory records."
    risk_level = RiskLevel.LOW

    async def execute(self, action: str = "list", key: Optional[str] = None, value: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            act = str(action).lower().strip()
            mem = MemoryService()

            if act in ("list", "show", "get_all", "listele", "oku"):
                facts = mem.get_all_user_facts()
                if not facts:
                    return ToolResult(success=True, output="🧠 **[HAFIZA]**: Kayıtlı kullanıcı bilgisi bulunamadı.")
                
                lines = [f"• **{k}**: `{v}`" for k, v in facts.items()]
                return ToolResult(
                    success=True,
                    output="🧠 **[KAYITLI KULLANICI HAFIZASI BİLGİLERİ]**:\n\n" + "\n".join(lines),
                    metadata={"facts_count": len(facts), "facts": facts}
                )

            elif act in ("set", "add", "save", "güncelle", "kaydet"):
                clean_key = str(key or "").strip()
                clean_val = str(value or "").strip()
                if not clean_key or not clean_val:
                    return ToolResult(success=False, output=None, error="Hafızaya kaydetmek için 'key' ve 'value' gereklidir.")
                
                mem.set_fact(clean_key, clean_val)
                return ToolResult(
                    success=True,
                    output=f"🧠 **[HAFIZA GÜNCELLENDİ]**: `{clean_key}` ➔ `{clean_val}` bilgisi hafızaya kaydedildi."
                )

            elif act in ("forget", "delete", "remove", "sil"):
                clean_key = str(key or "").strip()
                if not clean_key:
                    return ToolResult(success=False, output=None, error="Silinecek hafıza kaydı için 'key' parametresi gereklidir.")
                
                deleted = mem.delete_fact(clean_key)
                if deleted:
                    return ToolResult(success=True, output=f"🧠 **[HAFIZA BİLGİSİ SİLİNDİ]**: `{clean_key}` kaydı veritabanından temizlendi.")
                return ToolResult(success=False, output=None, error=f"Hafızada '{clean_key}' adında bir kayıt bulunamadı.")

            return ToolResult(success=False, output=None, error=f"Bilinmeyen hafıza eylemi: {action}")

        except Exception as e:
            logger.error(f"MemoryInspector error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
