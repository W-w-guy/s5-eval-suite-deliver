# -*- coding: utf-8 -*-
"""把合同正文渲染成三种【真实载体】：
  text_pdf     —— 手写 PDF，Type0/Identity-H + 子集嵌入 TrueType，带 ToUnicode，文字可提取
  scanned_pdf  —— PIL 把正文画成位图再存 PDF，纯图像无文字层（模拟扫描/拍照）
  docx         —— 纯 stdlib zipfile + OOXML，不依赖 python-docx
依赖：text_pdf 需 fontTools（仅生成侧）；scanned_pdf 需 Pillow；docx 零依赖。
"""
import io, os, re, zipfile

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
]


def find_font():
    for f in FONT_CANDIDATES:
        if os.path.isfile(f):
            return f
    raise RuntimeError("找不到中文字体，候选=%s" % FONT_CANDIDATES)


# ---------------- docx（stdlib） ----------------
def write_docx(lines, path, title="服务合同"):
    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    ps = "".join(
        '<w:p><w:r><w:rPr><w:rFonts w:eastAsia="SimSun"/></w:rPr>'
        '<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % esc(l) for l in lines)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>%s<w:sectPr/></w:body></w:document>' % ps)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    def zi(name):
        # 固定时间戳与 create_system，保证 docx 字节级可复现（跨平台一致）
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 0
        info.external_attr = 0o600 << 16
        return info
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zi("[Content_Types].xml"), ct)
        z.writestr(zi("_rels/.rels"), rels)
        z.writestr(zi("word/document.xml"), doc)


# ---------------- text_pdf（手写 PDF + 子集字体） ----------------
def _subset_font(fontpath, chars):
    from fontTools.ttLib import TTFont
    from fontTools import subset
    font = TTFont(fontpath, fontNumber=0)
    # 关键：关闭保存时自动刷新时间戳，否则每次子集化的字节都不同
    font.recalcTimestamp = False
    opts = subset.Options()
    import logging
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    opts.drop_tables += ["FFTM", "meta"]
    opts.notdef_outline = True
    ss = subset.Subsetter(options=opts)
    ss.populate(unicodes=[ord(c) for c in chars])
    ss.subset(font)
    # 固定 head.modified / created，否则每次子集化的字节都不同（跨进程不可复现）
    font["head"].modified = 0
    if hasattr(font["head"], "created"):
        font["head"].created = 0
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    f2 = TTFont(io.BytesIO(data))
    cmap = f2.getBestCmap()
    hmtx = f2["hmtx"]
    upem = f2["head"].unitsPerEm
    gid_of, width_of = {}, {}
    for ch in chars:
        gn = cmap.get(ord(ch))
        if not gn:
            continue
        gid = f2.getGlyphID(gn)
        gid_of[ch] = gid
        width_of[gid] = int(round(hmtx[gn][0] * 1000.0 / upem))
    return data, gid_of, width_of


def write_text_pdf(lines, path, fontpath=None, size=10.5, leading=15.5, margin=56):
    fontpath = fontpath or find_font()
    chars = "".join(lines) + " "
    fdata, gid_of, width_of = _subset_font(fontpath, sorted(set(chars)))
    W, H = 595, 842
    ops = []
    y = H - margin
    for ln in lines:
        if y < margin:
            break
        hexs = "".join("%04X" % gid_of.get(c, 0) for c in ln)
        ops.append("BT /F1 %.2f Tf 1 0 0 1 %d %.2f Tm <%s> Tj ET" % (size, margin, y, hexs))
        y -= leading
    content = "\n".join(ops).encode("latin-1")
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objs[3] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
               "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>" % (W, H)).encode("latin-1")
    objs[4] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    objs[5] = b"<< /Type /Font /Subtype /Type0 /BaseFont /SubCJK /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 9 0 R >>"
    objs[6] = ("<< /Type /Font /Subtype /CIDFontType2 /BaseFont /SubCJK /CIDSystemInfo "
               "<< /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 7 0 R "
               "/DW 1000 /W [%s] /CIDToGIDMap /Identity >>"
               % " ".join("%d [%d]" % (g, w) for g, w in sorted(width_of.items()))).encode("latin-1")
    objs[7] = ("<< /Type /FontDescriptor /FontName /SubCJK /Flags 4 /FontBBox [0 -200 1000 900] "
               "/ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 /FontFile2 8 0 R >>").encode("latin-1")
    objs[8] = b"<< /Length %d /Length1 %d >>\nstream\n" % (len(fdata), len(fdata)) + fdata + b"\nendstream"
    bf = []
    for ch, g in sorted(gid_of.items(), key=lambda kv: kv[1]):
        bf.append("<%04X> <%04X>" % (g, ord(ch)))
    blocks = []
    for i in range(0, len(bf), 100):
        blocks.append("%d beginbfchar\n%s\nendbfchar" % (len(bf[i:i + 100]), "\n".join(bf[i:i + 100])))
    cmap = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            + "\n".join(blocks) +
            "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n").encode("latin-1")
    objs[9] = b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream"
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = {}
    for i in range(1, 10):
        offs[i] = len(out)
        out += b"%d 0 obj\n" % i + objs[i] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 10\n0000000000 65535 f \n"
    for i in range(1, 10):
        out += b"%010d 00000 n \n" % offs[i]
    out += b"trailer\n<< /Size 10 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref
    open(path, "wb").write(bytes(out))


# ---------------- scanned_pdf（纯图像） ----------------
def write_scanned_pdf(lines, path, skew=0.0, fontpath=None):
    from PIL import Image, ImageDraw, ImageFont
    fontpath = fontpath or find_font()
    fnt = ImageFont.truetype(fontpath, 22)
    img = Image.new("L", (1240, 1754), 246)
    d = ImageDraw.Draw(img)
    y = 110
    for ln in lines:
        if y > 1700:
            break
        d.text((100, y), ln, font=fnt, fill=30)
        y += 34
    if skew:
        img = img.rotate(skew, resample=Image.BICUBIC, fillcolor=246, expand=False)
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150.0)
    raw = buf.getvalue()
    # PIL 会写入当前时间的 /CreationDate、/ModDate；替换成等长固定值（长度必须一致，
    # 否则 xref 偏移全部错位，pypdf 会报 incorrect startxref pointer）。
    def _fix(m):
        head, orig = m.group(1), m.group(2)
        if len(orig) < 16:
            return m.group(0)
        tail = re.sub(rb"\d", b"0", orig[16:])      # 时区部分数字清零，符号与引号保留
        return head + b"D:20260101000000" + tail + b")"
    raw2 = re.sub(rb"(/(?:CreationDate|ModDate) \()([^)]*)\)", _fix, raw)
    assert len(raw2) == len(raw), "日期替换改变了 PDF 长度（%d -> %d）" % (len(raw), len(raw2))
    with open(path, "wb") as f:
        f.write(raw2)
