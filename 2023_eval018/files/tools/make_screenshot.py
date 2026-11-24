# -*- coding: utf-8 -*-
"""把 mock 输出（reports/doc_v1.json）里的指标与【错而未标红明细】渲染成报告截图 PNG。

这是「报告截图」交付物：内容全部来自 runner 的产物，不是手绘。
依赖 Pillow；找不到中文字体时退化为英文标签并返回 rc=2（不静默出空图）。
"""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc",
         "/usr/share/fonts/truetype/arphic/uming.ttc",
         "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"]


def main(tag="v1"):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in FONTS if os.path.isfile(f)), None)
    if not fp:
        print("找不到中文字体，拒绝生成空图")
        return 2
    data = json.load(open(os.path.join(HERE, "reports", "doc_%s.json" % tag), encoding="utf-8"))
    m, rows = data["metrics"], data["rows"]
    f_t = ImageFont.truetype(fp, 30)
    f_h = ImageFont.truetype(fp, 22)
    f_b = ImageFont.truetype(fp, 19)
    W, H = 1180, 900
    img = Image.new("RGB", (W, H), (252, 252, 250))
    d = ImageDraw.Draw(img)
    y = 24
    d.text((36, y), "评测报告截图（由 reports/doc_%s.json 渲染）" % tag, font=f_t, fill=(20, 20, 20)); y += 46
    d.text((36, y), "被测：echo mock（正则抽取 + 保守自检）｜用例 %d 份" % m["cases"], font=f_b, fill=(90, 90, 90)); y += 40
    d.rectangle([36, y, W - 36, y + 118], outline=(200, 200, 200))
    d.text((52, y + 12), "指标", font=f_h, fill=(0, 0, 0))
    d.text((240, y + 12), "实测", font=f_h, fill=(0, 0, 0))
    d.text((400, y + 12), "门槛", font=f_h, fill=(0, 0, 0))
    d.text((560, y + 12), "判定", font=f_h, fill=(0, 0, 0))
    yy = y + 46
    for label, key, th, ok in (
            ("字段级准确率", "field_accuracy", 0.90, m["field_accuracy"] >= 0.90),
            ("错字段标红召回", "flag_recall", 0.95, m["flag_recall"] >= 0.95),
            ("错而未标红的 critical", "critical_unflagged_total", 0, m["critical_unflagged_total"] == 0)):
        d.text((52, yy), label, font=f_b, fill=(30, 30, 30))
        d.text((240, yy), str(round(m[key], 4) if isinstance(m[key], float) else m[key]), font=f_b, fill=(30, 30, 30))
        d.text((400, yy), "≥%s" % th if th else "=0", font=f_b, fill=(30, 30, 30))
        d.text((560, yy), "通过" if ok else "未通过", font=f_b, fill=(0, 120, 0) if ok else (190, 0, 0))
        yy += 26
    y += 132
    d.text((36, y), "错而未标红明细（逐用例列出字段，供人工复核队列）", font=f_h, fill=(0, 0, 0)); y += 34
    d.line([36, y, W - 36, y], fill=(180, 180, 180)); y += 8
    d.text((52, y), "用例", font=f_b, fill=(60, 60, 60))
    d.text((180, y), "类型", font=f_b, fill=(60, 60, 60))
    d.text((320, y), "未标红字段", font=f_b, fill=(60, 60, 60))
    d.text((700, y), "其中 critical", font=f_b, fill=(60, 60, 60))
    y += 28
    listed = [r for r in rows if r["wrong_unflagged"]]
    for r in listed[:14]:
        d.text((52, y), r["case_id"], font=f_b, fill=(30, 30, 30))
        d.text((180, y), r["kind"], font=f_b, fill=(30, 30, 30))
        d.text((320, y), ", ".join(r["wrong_unflagged"]), font=f_b, fill=(30, 30, 30))
        d.text((700, y), ", ".join(r["critical_unflagged"]) or "-", font=f_b, fill=(30, 30, 30))
        y += 26
    if not listed:
        d.text((52, y), "（无）", font=f_b, fill=(30, 30, 30)); y += 26
    y += 10
    d.text((36, y), "合计：识别错误字段 %d 个，其中未标红 %d 个，critical 未标红 %d 个"
           % (m["wrong_total"], m["wrong_unflagged_total"], m["critical_unflagged_total"]),
           font=f_b, fill=(20, 20, 20))
    out = os.path.join(HERE, "reports", "doc_%s_unflagged_screenshot.png" % tag)
    img.save(out)
    print("screenshot=%s (%dx%d)" % (out, img.size[0], img.size[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "v1"))
