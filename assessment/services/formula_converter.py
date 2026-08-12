"""OMML (Office Math) -> MathML konverter.

Rasmiy OMML2MML.XSL o'rniga keng tarqalgan OMML elementlarini qamrab
oluvchi yengil rekursiv konverter: kasr (m:f), daraja (m:sSup),
indeks (m:sSub), ikkalasi (m:sSubSup), ildiz (m:rad), yig'indi/integral
(m:nary), qavslar (m:d), funksiya (m:func), run matni (m:r/m:t).
"""
import re

try:
    from lxml import etree
    _HAS_LXML = True
except Exception:  # pragma: no cover
    _HAS_LXML = False

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def _local(el):
    tag = el.tag
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_TOKEN_RE = re.compile(r"\d+\.?\d*|[^\W\d_]+|\s+|[^\w\s]", re.UNICODE)


def _tokens_to_mathml(text):
    parts = []
    for tok in _TOKEN_RE.findall(text or ""):
        if tok.isspace():
            continue
        if tok[0].isdigit():
            parts.append(f"<mn>{_esc(tok)}</mn>")
        elif tok[0].isalpha():
            parts.append(f"<mi>{_esc(tok)}</mi>")
        else:
            parts.append(f"<mo>{_esc(tok)}</mo>")
    return "".join(parts)


class OMMLToMathMLConverter:
    def __init__(self):
        self.available = _HAS_LXML

    def convert(self, omml_xml: str) -> str:
        if not _HAS_LXML or not omml_xml:
            return ""
        try:
            data = omml_xml.encode("utf-8") if isinstance(omml_xml, str) else omml_xml
            root = etree.fromstring(data)
        except Exception:
            return ""
        body = self._children(root)
        if not body.strip() or body == "<mrow/>":
            return ""
        return ('<math xmlns="http://www.w3.org/1998/Math/MathML" '
                f'display="inline">{body}</math>')

    def _children(self, el, wrap=False):
        out = []
        for child in el:
            frag = self._node(child)
            if frag:
                out.append(frag)
        joined = "".join(out)
        if wrap and len(out) > 1:
            return f"<mrow>{joined}</mrow>"
        return joined or "<mrow/>"

    def _arg(self, parent, name):
        el = parent.find(M + name)
        if el is None:
            return "<mrow/>"
        return self._children(el, wrap=True)

    def _node(self, el):
        name = _local(el)
        if name.endswith("Pr") or name in ("chr", "begChr", "endChr", "degHide", "val", "pos", "ctrlPr"):
            return ""
        if name in ("oMath", "oMathPara", "e", "num", "den", "sup", "sub",
                    "deg", "fName", "lim", "groupChr", "limLow", "limUpp"):
            return self._children(el, wrap=True)
        if name == "r":
            txt = "".join(t.text or "" for t in el.findall(M + "t"))
            return _tokens_to_mathml(txt)
        if name == "t":
            return _tokens_to_mathml(el.text or "")
        if name == "f":
            return f"<mfrac>{self._arg(el, 'num')}{self._arg(el, 'den')}</mfrac>"
        if name == "sSup":
            return f"<msup>{self._arg(el, 'e')}{self._arg(el, 'sup')}</msup>"
        if name == "sSub":
            return f"<msub>{self._arg(el, 'e')}{self._arg(el, 'sub')}</msub>"
        if name == "sSubSup":
            return f"<msubsup>{self._arg(el, 'e')}{self._arg(el, 'sub')}{self._arg(el, 'sup')}</msubsup>"
        if name == "rad":
            deg = el.find(M + "deg")
            deg_body = self._children(deg, wrap=True) if deg is not None and len(deg) else ""
            if deg_body:
                return f"<mroot>{self._arg(el, 'e')}{deg_body}</mroot>"
            return f"<msqrt>{self._arg(el, 'e')}</msqrt>"
        if name == "nary":
            chr_el = el.find(M + "naryPr/" + M + "chr")
            op = chr_el.get(M + "val") if chr_el is not None else None
            op = op or "\u222B"
            sub = el.find(M + "sub")
            sup = el.find(M + "sup")
            sub_b = self._children(sub, wrap=True) if sub is not None and len(sub) else ""
            sup_b = self._children(sup, wrap=True) if sup is not None and len(sup) else ""
            big = "\u2211\u220F\u22C3\u22C2"
            container = "munderover" if op in big else "msubsup"
            if sub_b and sup_b:
                script = f"<{container}><mo>{_esc(op)}</mo>{sub_b}{sup_b}</{container}>"
            elif sub_b:
                sc = "munder" if op in big else "msub"
                script = f"<{sc}><mo>{_esc(op)}</mo>{sub_b}</{sc}>"
            else:
                script = f"<mo>{_esc(op)}</mo>"
            return f"<mrow>{script}{self._arg(el, 'e')}</mrow>"
        if name == "d":
            dpr = el.find(M + "dPr")
            beg, end = "(", ")"
            if dpr is not None:
                bc = dpr.find(M + "begChr")
                ec = dpr.find(M + "endChr")
                if bc is not None and bc.get(M + "val") is not None:
                    beg = bc.get(M + "val")
                if ec is not None and ec.get(M + "val") is not None:
                    end = ec.get(M + "val")
            inner = "".join(self._children(e, wrap=True) for e in el.findall(M + "e"))
            return f"<mrow><mo>{_esc(beg)}</mo>{inner}<mo>{_esc(end)}</mo></mrow>"
        if name == "func":
            return f"<mrow>{self._arg(el, 'fName')}<mo>&#8289;</mo>{self._arg(el, 'e')}</mrow>"
        if name in ("bar", "acc", "box", "borderBox"):
            return self._arg(el, "e")
        return self._children(el)
