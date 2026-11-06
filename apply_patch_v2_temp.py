import re

with open('agent/dispatcher.py', encoding='utf-8') as f:
    content = f.read()

# Regex ile esnek eslesme - whitespace farklarina karsi dayanikli
pattern = re.compile(
    r'#\s*3\.\s*HAFIZA SORGULAMA\s*\n\s*if any\(kw in lower for kw in \[.*?\]\):',
    re.DOTALL
)

match = pattern.search(content)
if not match:
    print('REGEX EŞLEŞMEDİ - dosyada bu blok farklı şekilde yazılmış olabilir')
else:
    print('BULUNDU:')
    print(repr(match.group(0)))
    print('---')
    new_block = '''# 3. HAFIZA SORGULAMA (GUVENLI SURUM - substring yerine intent)
        _mem_negative = ["kuantum", "ram", "rom", "bellek kartı", "hafıza kartı", "cache", "önbellek", "profesör", "doktor", "motor", "teori", "makale"]
        _mem_positive = ["hafızadaki bilgi", "benim hakkımda ne biliyorsun", "bilgilerimi listele", "kullanıcı bilgilerimi", "beni hatırlıyor musun", "hafızamda ne var"]
        _is_mem_query = (not any(n in lower for n in _mem_negative)) and any(p in lower for p in _mem_positive)
        if _is_mem_query:'''
    content_new = pattern.sub(new_block, content, count=1)
    with open('agent/dispatcher.py', 'w', encoding='utf-8') as f:
        f.write(content_new)
    print('PATCH BASARIYLA UYGULANDI')
