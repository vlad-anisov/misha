"""Два PDF-документа для передачи:
  1_Кратко_о_раме.pdf                 — краткий обзор для любого читателя (что это, как выглядит, как регулируется,
                                          какие материалы и сколько, какие работы);
  2_Документация_для_изготовления.pdf — полный комплект: ведомость документов, все разделы docs/, таблицы,
                                          ведомость материалов, расчёт, листы чертежей.
Запуск после build.py / bom.py / fabrication.py / drawings.py:  python cad/report.py
"""
import csv
import datetime
import os
import re
import sys
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

sys.path.insert(0, os.path.dirname(__file__))
from params import (BASE_L, BASE_W, D_MAX, D_MIN, D_STEP, DECK_D, DECK_W, H_MAX, H_MIN, H_STEP,  # noqa: E402
                    PEDAL_ANGLES as PEDAL_A, PEDAL_PZ, PEDAL_XP, SEAT_XC, SIDE_ZP)

ROOT = os.path.join(os.path.dirname(__file__), "..")
REV = "4"
OUT_BRIEF = os.path.join(ROOT, "1_Кратко_о_раме.pdf")
OUT_FULL = os.path.join(ROOT, "2_Документация_для_изготовления.pdf")

# ---------------------------------------------------------------- шрифты и стили
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DV-B", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DV-I", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DV-BI", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVM", FD + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

ACC = colors.HexColor("#1f4e79")
LIGHT = colors.HexColor("#e8eef5")
S = {
    "title": ParagraphStyle("title", fontName="DV-B", fontSize=22, leading=27, textColor=ACC, spaceAfter=6),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=11, leading=15, textColor=colors.HexColor("#444444")),
    "h1": ParagraphStyle("h1", fontName="DV-B", fontSize=15, leading=19, textColor=ACC, spaceBefore=4, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="DV-B", fontSize=11.5, leading=15, textColor=ACC, spaceBefore=8, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="DV-B", fontSize=9.5, leading=12.5, spaceBefore=6, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="DV", fontSize=9, leading=12.5, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="DV", fontSize=9, leading=12.5, leftIndent=12, bulletIndent=3, spaceAfter=1.5),
    "note": ParagraphStyle("note", fontName="DV", fontSize=8.5, leading=11.5, backColor=LIGHT, borderPadding=5,
                           leftIndent=5, rightIndent=5, spaceBefore=4, spaceAfter=8),
    "warn": ParagraphStyle("warn", fontName="DV", fontSize=9, leading=12.5, backColor=colors.HexColor("#fdecea"),
                           borderColor=colors.HexColor("#c0392b"), borderWidth=0.8, borderPadding=6, leftIndent=6,
                           rightIndent=6, spaceBefore=6, spaceAfter=10),
    "cap": ParagraphStyle("cap", fontName="DV", fontSize=7.5, leading=9.5, alignment=TA_CENTER,
                          textColor=colors.HexColor("#555555"), spaceAfter=6),
    "td": ParagraphStyle("td", fontName="DV", fontSize=7.5, leading=9.5),
    "th": ParagraphStyle("th", fontName="DV-B", fontSize=7.5, leading=9.5, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="DVM", fontSize=7.5, leading=9.5, backColor=LIGHT, borderPadding=4,
                           spaceAfter=6),
}
PAGE_W = A4[0] - 30 * mm


def P(text, st="p"):
    return Paragraph(text, S[st])


def bullets(items, st="li"):
    return [Paragraph(t, S[st], bulletText="•") for t in items]


def table(rows, widths=None, head=True, font=None):
    """rows — списки строк (разметка reportlab). widths — доли ширины."""
    td, th = S["td"], S["th"]
    if font:
        td = ParagraphStyle("tdx", parent=td, fontSize=font, leading=font * 1.3)
        th = ParagraphStyle("thx", parent=th, fontSize=font, leading=font * 1.3)
    data = [[Paragraph(str(c), th if (head and i == 0) else td) for c in r] for i, r in enumerate(rows)]
    ncol = max(len(r) for r in rows)
    if widths is None:
        lens = [max(min(len(re.sub(r"<[^>]+>", "", str(r[j]))) if j < len(r) else 0, 60) for r in rows) + 4
                for j in range(ncol)]
        widths = [x / sum(lens) for x in lens]
    t = Table(data, colWidths=[w * PAGE_W for w in widths], repeatRows=1 if head else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9aa7b5")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), ACC))
    t.setStyle(TableStyle(style))
    return t


def img(path, width=PAGE_W, max_h=None, caption=None):
    from PIL import Image as PI
    full = os.path.join(ROOT, path)
    w, h = PI.open(full).size
    W = width
    H = W * h / w
    if max_h and H > max_h:
        H = max_h
        W = H * w / h
    out = [Image(full, width=W, height=H)]
    if caption:
        out.append(P(caption, "cap"))
    return out


def footer(title):
    def draw(canv, doc):
        canv.saveState()
        canv.setFont("DV", 7)
        canv.setFillColor(colors.HexColor("#777777"))
        canv.drawString(15 * mm, 9 * mm, f"Рама автосимулятора · ревизия {REV} · {title}")
        canv.drawRightString(A4[0] - 15 * mm, 9 * mm, f"стр. {doc.page}")
        canv.restoreState()
    return draw


def make_doc(path, title):
    return SimpleDocTemplate(path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                             bottomMargin=16 * mm, title=title, author="Проект misha", subject="Рама автосимулятора")


# ---------------------------------------------------------------- данные о материалах
def read_csv(name):
    with open(os.path.join(ROOT, "fabrication", name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# дополнительно к модели: комплект вкладышей 1.5 и 2.5 мм и 4 проставки Л23 (см. docs/05 §5.1)
EXTRA = [("Л05", 1.5, 4), ("Л06", 1.5, 4), ("Л26", 1.5, 2), ("Л27", 1.5, 2),
         ("Л05", 2.5, 4), ("Л06", 2.5, 4), ("Л26", 2.5, 2), ("Л27", 2.5, 2), ("Л23", 8.0, 4)]
STOCK_KG_M = {"Труба 40x40x3": 3.30, "Труба 50x50x3": 4.25, "Квадрат сплошной 40x40": 12.56}


def materials():
    laser = read_csv("laser_parts.csv")
    by_pos = {r["pos"]: r for r in laser}
    sheet = defaultdict(lambda: [0, 0.0])          # толщина -> [шт., м² по габаритам]
    for r in laser:
        a, b = (float(v) for v in r["size_mm"].split("x"))
        q = int(r["qty"])
        sheet[float(r["thickness_mm"])][0] += q
        sheet[float(r["thickness_mm"])][1] += a * b * q / 1e6
    for pos, t, q in EXTRA:
        a, b = (float(v) for v in by_pos[pos]["size_mm"].split("x"))
        sheet[t][0] += q
        sheet[t][1] += a * b * q / 1e6
    stock = defaultdict(float)
    for r in read_csv("cut_list.csv"):
        key = r["stock"].split(" (")[0]
        stock[key] += float(r["length_mm"]) * int(r["qty"]) / 1000
    return laser, dict(sheet), dict(stock)


def fasteners():
    rows, on = [], False
    for line in open(os.path.join(ROOT, "docs/generated/bom.md"), encoding="utf-8"):
        if line.startswith("## Крепёж"):
            on = True
            continue
        if on and line.startswith("|") and not line.startswith("|---") and "Изделие" not in line:
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            rows.append((c[0], int(c[1])))
        elif on and line.startswith("**"):
            break
    return rows


# ---------------------------------------------------------------- 1. краткий обзор
def brief():
    laser, sheet, stock = materials()
    story = []
    # --- стр. 1
    story += [P("Регулируемая рама автосимулятора", "title"),
              P(f"Краткое описание для всех, кто будет её делать или заказывать · ревизия {REV} · "
                f"{datetime.date.today():%d.%m.%Y}", "sub"), Spacer(1, 6)]
    story += img("drawings/3d/nominal.png", caption="Общий вид (среднее положение регулировок). Руль, сиденье и "
                                                    "человек — условные, для проверки посадки.")
    story += [P("<b>Что это.</b> Стальная сварная рама для домашнего симулятора: на ней крепятся руль, педали, "
                "сиденье, шифтер и ручник. Почти всё регулируется под рост пилота. Рама сварная и очень жёсткая: "
                "руль и педали не гуляют даже при сильном торможении и мощной рулевой базе. Делается "
                "<b>одна штука</b>, не серия."),
              P("<b>Как устроено изготовление.</b> Детали с отверстиями вырезает лазер по готовым файлам. "
                "Мастер их не размечает и почти не сверлит: только нарезает трубы, собирает детали на болтах "
                "и сваривает. Гнуть ничего не нужно. Болты, гайки и ножки покупаются готовые."),
              P("<b>Статус: проект почти готов, но не закончен.</b> Конструкция проверена по 3D-модели. "
                "До заказа резки осталось решить 4 вопроса (раздел 7): сварная рама или с минимумом сварки, "
                "ответы цеха, какая рулевая база, какое сиденье.", "warn")]
    story.append(table([
        ["Параметр", "Значение"],
        ["Размер основания", f"{BASE_L:.0f} × {BASE_W:.0f} мм (по ножкам ≈ 686 мм)"],
        ["Масса стали", "≈ 118 кг"],
        ["Материал", "лист стали 8 мм (одна деталь 12 мм), квадратные трубы 40×40 и 50×50 (стенка 3 мм), "
                     "сплошной брусок 40×40, тонкий лист 2 мм на прокладки"],
        ["Как фиксируются регулировки", "болт М12 в круглом отверстии — сдвинуться не может, пока болт на месте"],
        ["Работа мастера", "нарезать трубы, сварить, покрасить; ≈ 15–20 часов (без лазера)"],
    ], widths=[0.3, 0.7]))
    story.append(PageBreak())

    # --- стр. 2: из чего состоит
    story += [P("1. Из чего состоит рама", "h1")]
    story += img("drawings/S01_isometric.png", max_h=120 * mm, caption="Лист S01 — общий вид с размерами")
    story += bullets([
        "<b>Основание</b> — прямоугольник из трубы 40×40 на 6 ножках с регулировкой по высоте (под неровный пол).",
        "<b>Стойки руля</b> — две вертикальные трубы 50×50 с косынками и подкосами. Внутрь вставлены "
        "<b>выдвижные бруски 40×40</b> — так меняется высота руля.",
        "<b>Площадка руля</b> — плита, на которую ставится рулевая база. Двигается вперёд-назад. "
        "Базу можно крепить снизу или спереди (съёмный кронштейн).",
        "<b>Педальная площадка</b> — наклоняется и двигается вперёд-назад по основанию.",
        "<b>Две поперечины под сиденье</b> — двигаются вперёд-назад; к ним крепятся салазки сиденья.",
        "<b>Кронштейн шифтера и ручника</b> — съёмный, ставится справа или слева, регулируется по высоте.",
    ])
    story.append(PageBreak())

    # --- стр. 3: регулировки
    story += [P("2. Что регулируется", "h1")]
    story.append(table([
        ["Что", "Диапазон", "Шаг", "Как"],
        ["Высота руля (верх площадки от пола)", f"{H_MIN:.0f}…{H_MAX:.0f} мм", f"{H_STEP:.0f} мм",
         "выдвижной брусок, 2 болта на стойку"],
        ["Руль вперёд-назад", f"{D_MIN:+.0f}…{D_MAX:+.0f} мм", f"{D_STEP:.0f} мм", "4 болта"],
        ["Наклон педалей", f"{PEDAL_A[0]:.0f}…{PEDAL_A[-1]:.0f}°", "10°", "ось + 1 болт с каждой стороны"],
        ["Педали вперёд-назад", f"ход {PEDAL_XP[-1] - PEDAL_XP[0]:.0f} мм", "25 мм", "по 3 болта с каждой стороны"],
        ["Высота педалей", f"{PEDAL_PZ[0]:.0f} или {PEDAL_PZ[1]:.0f} мм (ось)", "—", "второй ряд отверстий"],
        ["Сиденье вперёд-назад", f"{SEAT_XC[0]:.0f}…{SEAT_XC[-1]:.0f} мм + салазки", "25 мм + плавно",
         "поперечины по 3 болта на конец"],
        ["Высота / наклон сиденья", "проставками 8 мм", "8 мм", "полосы под поперечины"],
        ["Шифтер / ручник", f"высота {SIDE_ZP[0]:.0f}…{SIDE_ZP[-1]:.0f} мм, справа или слева", "25 мм",
         "выдвижной брусок, 2 болта"],
    ], widths=[0.3, 0.27, 0.13, 0.3]))
    story += [Spacer(1, 6), P("<b>Крайние положения руля</b> (проверено по 3D-модели: ничего ни во что не упирается, "
                              "каждый болт можно вынуть ключом):", "p")]
    cells = []
    for f, cap in (("wheel_low_fwd", f"низ {H_MIN:.0f}, вперёд"), ("wheel_low_back", f"низ {H_MIN:.0f}, назад"),
                   ("wheel_high_fwd", f"верх {H_MAX:.0f}, вперёд"), ("wheel_high_back", f"верх {H_MAX:.0f}, назад")):
        cells.append(img(f"drawings/3d/{f}.png", width=PAGE_W / 2 - 4, caption=cap))
    t = Table([[cells[0], cells[1]], [cells[2], cells[3]]], colWidths=[PAGE_W / 2] * 2)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    story.append(t)
    story.append(PageBreak())

    # --- стр. 4: как работают регулировки
    story += [P("3. Как работает регулировка (одна идея на всю раму)", "h1"),
              P("Везде одинаково: в неподвижной части — <b>ряд круглых отверстий через 25 мм</b>, в подвижной — "
                "<b>два отверстия</b>. Совместили нужные отверстия, вставили болты, затянули. Пазов, по которым "
                "что-то может проскользнуть, нет."),
              ]
    story += bullets([
        "<b>Высота руля</b> — телескоп: сплошной брусок 40×40 ходит внутри трубы 50×50. Щель между ними "
        "(≈2 мм с каждой стороны) заполнена тонкими стальными <b>прокладками-вкладышами</b> — руль не болтается. "
        "Поднять/опустить можно в одиночку: снизу вкручивается винт-домкрат М16.",
        "<b>Площадка руля, педали, сиденье</b> — стальная полоса 50×8 с отверстиями (<b>«гребень»</b>) и "
        "охватывающая её <b>«вилка»</b>: приваренная щека + съёмная прижимная пластина. Болты проходят сквозь всё.",
        "<b>Гайки самоконтрящиеся</b> (цельнометаллические, ISO 7042) — не откручиваются от вибрации базы. "
        "Затяжка 80 Н·м динамометрическим ключом.",
    ])
    story += img("drawings/S05_height_mechanism.png", caption="Лист S05 — механизм высоты руля")
    story.append(PageBreak())
    story += img("drawings/S06_foreaft_mechanism.png", caption="Лист S06 — механизм «руль вперёд-назад»")
    story += img("drawings/S08_pedal_unit.png", caption="Лист S08 — педальный узел")
    story.append(PageBreak())

    # --- стр. 5: материалы
    story += [P("4. Материалы и сколько их нужно", "h1"),
              P("Количество посчитано по 3D-модели. При покупке добавить ≈10–15 % на рез и брак. "
                "Сталь — обычная конструкционная (Ст3 / S235).", "p"), P("Прокат (трубы и брусок)", "h2")]
    rows = [["Что", "Пояснение", "Нужно по модели", "Купить", "Масса, кг"]]
    expl = {"Труба 40x40x3": "квадратная труба 40×40 мм, стенка 3 мм",
            "Труба 50x50x3": "квадратная труба 50×50 мм, стенка 3 мм",
            "Квадрат сплошной 40x40": "сплошной брусок 40×40 мм (не труба); лучше калиброванный, "
                                      "можно обычный горячекатаный"}
    buy = {"Труба 40x40x3": "8 м", "Труба 50x50x3": "2,5–3 м", "Квадрат сплошной 40x40": "1,1–1,2 м"}
    for k, v in stock.items():
        rows.append([k.replace("x", "×"), expl.get(k, ""), f"{v:.2f} м", buy.get(k, "—"),
                     f"{v * STOCK_KG_M.get(k, 0):.0f}"])
    story.append(table(rows, widths=[0.2, 0.36, 0.15, 0.13, 0.16]))
    story += [P("Лист (режет лазер)", "h2")]
    rows = [["Толщина", "Что из него", "Деталей, шт.", "Площадь деталей*, м²", "Масса*, кг"]]
    what = {8.0: "почти все плоские детали (гребни, косынки, щёки, площадки, фланцы)",
            12.0: f"одна деталь — площадка руля {DECK_W:.0f}×{DECK_D:.0f}",
            2.0: "вкладыши-прокладки телескопов", 1.5: "запасные вкладыши для подбора", 2.5: "запасные вкладыши для подбора"}
    for t_ in sorted(sheet, reverse=True):
        n, a = sheet[t_]
        rows.append([f"{t_:g} мм", what.get(t_, ""), str(n), f"{a:.2f}", f"{a * t_ * 7.85:.0f}"])
    story.append(table(rows, widths=[0.1, 0.48, 0.12, 0.16, 0.14]))
    a8 = sheet[8.0][1]
    story.append(P(f"* по габаритным прямоугольникам деталей, т.е. с запасом. Для листа 8 мм это ≈{a8:.1f} м² — "
                   f"примерно <b>один лист 1250×2500 мм</b> (3,1 м²) с учётом раскроя; лазерный цех обычно режет из "
                   f"своего листа и считает по факту. Лист 1,5/2,0/2,5 мм нужен совсем немного — обрезки.", "cap"))
    story += [P("Покупное (крепёж и ножки)", "h2")]
    rows = [["Изделие", "Шт. в раме"]] + [[a, str(b)] for a, b in fasteners()]
    rows.append(["Запас гаек ISO 7042 М12 на замену (меняются каждые ~5 перестановок)", "30"])
    story.append(table(rows, widths=[0.82, 0.18]))
    story.append(P("Болты — класс прочности 8.8, оцинкованные, с гладкой частью стержня (ISO 4014). Отверстия под "
                   "руль, педали, сиденье и шифтер сверлятся <b>после покупки этого оборудования</b> — по его шаблону.",
                   "p"))
    story.append(PageBreak())

    # --- стр. 6: работы
    story += [P("5. Какие работы нужны и кто их делает", "h1")]
    n8 = sum(int(r["qty"]) for r in laser)
    story.append(table([
        ["№", "Работа", "Что именно", "Кто"],
        ["1", "Лазерная резка листа", f"{len(laser) - 1} видов деталей + шаблон для сверления (≈{n8} шт.) по файлам DXF, отверстия Ø13; на каждой "
                                      "детали гравируется номер и стрелки «ПЕРЕД», «ВВЕРХ»", "лазерный цех"],
        ["2", "Резка труб в размер", "по таблице раскроя (≈20 кусков); подкосы — под углом",
         "лазерный труборез или мастер (пила)"],
        ["3", "Отверстия в трубах 50×50", "3 трубы, ряд отверстий Ø13 через 25 мм",
         "лазерный труборез (лучше) или сверлильный станок"],
        ["4", "Сверление бруска 40×40", "3 куска по 2 отверстия Ø13, по шаблону-кондуктору (вырезан лазером)",
         "мастер, сверлильный станок"],
        ["5", "Сварка", "по пошаговой инструкции: сначала собрать на болтах, потом прихватить, потом варить",
         "сварщик (полуавтомат)"],
        ["6", "Покраска", "зачистить, обезжирить, грунт + эмаль (или порошок); места под болтами не красить",
         "мастер / покрасочный цех"],
        ["7", "Сборка и настройка", "болты, ножки, подбор вкладышей, затяжка", "сам владелец"],
    ], widths=[0.05, 0.2, 0.5, 0.25]))
    story += [Spacer(1, 6), P("<b>Не нужно:</b> гибка листа, токарные работы, нарезание резьбы. Чтобы мастер не "
                              "ошибся, детали собираются <b>на болтах как в кондукторе</b> и только потом "
                              "свариваются: собранные на болтах детали физически не встанут неправильно."),
              P("<b>Что важно соблюсти сварщику</b> (подробно — в документации):", "p")]
    story += bullets([
        "расстояние между внутренними гранями левого и правого гребня — 532 мм (допуск −0/+3);",
        "стойки руля параллельны (≤ 0,5 мм на 300 мм);",
        "не приваривать прижимные пластины, вкладыши и бруски — они съёмные.",
    ])
    story += img("drawings/S12_laser_parts.png", max_h=110 * mm, caption="Лист S12 — все лазерные детали")
    story.append(PageBreak())

    # --- стр. 7: словарик
    story += [P("6. Словарик", "h1")]
    story.append(table([
        ["Слово", "Что это"],
        ["Лонжерон", "длинная труба основания (их две, по бокам)"],
        ["Поперечина", "труба поперёк рамы"],
        ["Гребень", "стальная полоса 50×8 мм с рядом отверстий через 25 мм, приварена сверху на трубу; по ней "
                    "переставляются педали, сиденье, площадка руля"],
        ["Щека, прижимная пластина", "две пластины по бокам гребня; щека приварена, пластина съёмная. "
                                     "Это одна и та же деталь — перепутать нельзя"],
        ["Башмак, седло, каретка", "узел «щека + пластина + болты», который охватывает гребень"],
        ["Телескоп", "труба 50×50 и выдвижной брусок 40×40 внутри неё"],
        ["Брусок (квадрат) 40×40", "сплошной стальной пруток квадратного сечения; продаётся на металлобазе, режется пилой"],
        ["Вкладыш", "тонкая стальная прокладка 1,5–2,5 мм внутри телескопа, убирает люфт"],
        ["Косынка", "треугольная или фигурная пластина-усилитель в углу соединения"],
        ["Подкос", "наклонная труба, держит стойку руля от раскачивания"],
        ["Кондуктор", "шаблон, по которому сверлят или собирают детали, чтобы всё совпало"],
        ["Прихватка", "короткие точки сварки, чтобы зафиксировать деталь перед полной сваркой"],
        ["ISO 7042", "цельнометаллическая самоконтрящаяся гайка — не откручивается от вибрации"],
        ["DXF", "файл контура детали для лазера (масштаб 1:1, мм)"],
        ["STEP, STL", "файлы 3D-модели: STEP — для конструктора/CAD, STL — для просмотра и 3D-печати"],
    ], widths=[0.25, 0.75]))
    story.append(PageBreak())

    # --- стр. 8: что не решено + состав документации
    story += [P("7. Что осталось решить (проект не закончен)", "h1"),
              P("<b>А. До заказа резки — обязательно:</b>", "h2")]
    story.append(table([
        ["№", "Вопрос", "Что от него зависит"],
        ["А1", "Сварная рама (как сейчас) или вариант с минимумом сварки", "все детали; сейчас — сварная"],
        ["А2", "Ответы цеха: труборез, лист 12 мм, брусок 40×40, точность отверстий",
         "возможно, поправить файлы для лазера"],
        ["А3", "Какая рулевая база (момент, крепление)", "отверстия под базу лучше сразу вырезать лазером; "
                                                         "расчёт сделан для базы до 25 Н·м"],
        ["А4", "Какое сиденье (на салазках или ковш с боковым креплением)",
         "для ковша нужны боковые кронштейны — пока не спроектированы"],
    ], widths=[0.06, 0.47, 0.47]))
    story += [P("<b>Б. Можно позже</b> (сверлится по месту или дозаказывается):", "h2")]
    story += bullets(["отверстия под педали, шифтер, ручник — после покупки;",
                      "наклон площадки руля (сейчас нет) — после выбора базы;",
                      "способ покраски; калиброванный или обычный брусок."])
    story += [P("<b>В. Чего у рамы нет</b> (бывает у готовых рам, можно добавить потом):", "h2")]
    story += bullets(["крепление монитора (исключено заданием — отдельная стойка на полу);",
                      "кронштейн блока питания базы и укладка кабелей; полка под клавиатуру, кнопочный блок;",
                      "упор для пяток; крепления вибромоторов; колёса/ручки для переноски (рама ≈118 кг)."])
    story += [P("<b>Г. После изготовления:</b>", "h2")]
    story += bullets(["сначала сделать <b>пробный узел</b> — одну стойку руля с бруском, проверить посадку;",
                      "проверить размеры после сварки (532 мм между гребнями, параллельность стоек);",
                      "подтянуть болты после 2–5 часов езды; нужен динамометрический ключ и головка 18 мм."])
    story.append(P("Подробно — раздел СИМ-01 полной документации и docs/07_status_open_items.md.", "cap"))
    story += [P("8. Полная документация", "h1"),
              P("Всё для изготовления — в файле <b>2_Документация_для_изготовления.pdf</b> и в папках репозитория:")]
    story.append(table([
        ["Что", "Где"],
        ["Пошаговая инструкция для сварщика, допуски, карта сварки", "раздел СИМ-06 полной документации"],
        ["Файлы для лазера (DXF), 28 деталей + кондуктор", "fabrication/dxf/"],
        ["Таблица деталей для лазера, таблица резки труб", "fabrication/laser_parts.csv, fabrication/cut_list.csv"],
        ["Чертежи (12 листов)", "drawings/simrig_concept_drawings.pdf"],
        ["3D-модель (STEP, STL)", "out/step/, out/stl/"],
        ["Ведомость материалов и крепежа", "docs/generated/bom.md"],
        ["Нагрузки и расчёт", "docs/03_loads_and_checks.md, docs/generated/calc_results.md"],
        ["Короткие вопросы цеху", "docs/06_questions_for_workshop.md"],
        ["Что осталось решить (подробно)", "docs/07_status_open_items.md"],
    ], widths=[0.55, 0.45]))
    story += [Spacer(1, 8), P("Вопросы цеху (коротко)", "h2")]
    story += bullets(["Что из работ 1–6 можете сделать вы, что нужно заказывать отдельно?",
                      "Есть ли лазерный труборез и сверлильный станок?",
                      "Какая сталь есть в наличии (лист 8 и 12 мм, трубы 40×40×3 и 50×50×3, брусок 40×40)?",
                      "Сколько будет стоить и сколько займёт времени?"])

    doc = make_doc(OUT_BRIEF, "Рама автосимулятора — кратко")
    doc.build(story, onFirstPage=footer("кратко"), onLaterPages=footer("кратко"))


# ---------------------------------------------------------------- markdown -> flowables
def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r'<font face="DVM" size="7.5">\1</font>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def md_flowables(path, shift=0):
    lines = open(os.path.join(ROOT, path), encoding="utf-8").read().splitlines()
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append(P(inline(" ".join(para))))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if st.startswith("```"):
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            out.append(Preformatted("\n".join(lines[i + 1:j]), S["code"]))
            i = j + 1
            continue
        if not st:
            flush()
        elif st.startswith("#"):
            flush()
            lvl = len(st) - len(st.lstrip("#"))
            out.append(P(inline(st.lstrip("#").strip()), ("h1", "h2", "h3", "h3")[min(lvl - 1 + shift, 3)]))
        elif st.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(P(inline(" ".join(b for b in buf if b)), "note"))
            continue
        elif st.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                r = lines[i].strip()
                if not re.match(r"^\|[\s\-:|]+\|$", r):
                    rows.append([inline(c.strip()) for c in r.strip("|").split("|")])
                i += 1
            n = max(len(r) for r in rows)
            rows = [r + [""] * (n - len(r)) for r in rows]
            out.append(table(rows, font=7 if n > 5 else None))
            out.append(Spacer(1, 5))
            continue
        elif re.match(r"^(\s*)([*\-]|\d+\.)\s+", ln):
            flush()
            m = re.match(r"^(\s*)([*\-]|\d+\.)\s+(.*)$", ln)
            text, ind = m.group(3), len(m.group(1))
            j = i + 1
            while j < len(lines) and lines[j].startswith(" ") and lines[j].strip() and \
                    not re.match(r"^\s*([*\-]|\d+\.)\s+", lines[j]):
                text += " " + lines[j].strip()
                j += 1
            b = "•" if m.group(2) in "*-" else m.group(2)
            stl = ParagraphStyle("lix", parent=S["li"], leftIndent=14 + ind * 4, bulletIndent=3 + ind * 4)
            out.append(Paragraph(inline(text), stl, bulletText=b))
            i = j
            continue
        else:
            para.append(st)
        i += 1
    flush()
    return out


# ---------------------------------------------------------------- 2. полная документация
FULL_DOCS = [  # (обозначение, наименование, файл в PDF, где лежит)
    ("СИМ-00", "Ведомость документов", None, "этот файл"),
    ("СИМ-01", "Статус проекта: что осталось решить", "docs/07_status_open_items.md", "docs/07_status_open_items.md"),
    ("СИМ-02", "Концепция и обоснование решений", "docs/01_concept.md", "docs/01_concept.md"),
    ("СИМ-03", "Регулируемые соединения: схемы, фиксация, долговечность", "docs/02_adjustable_joints.md", "docs/02_adjustable_joints.md"),
    ("СИМ-04", "Нагрузки, допущения, результаты проверок", "docs/03_loads_and_checks.md", "docs/03_loads_and_checks.md"),
    ("СИМ-05", "Параметры к уточнению после выбора оборудования", "docs/04_open_parameters.md", "docs/04_open_parameters.md"),
    ("СИМ-06", "Изготовление и сборка — инструкция для мастера", "docs/05_fabrication_assembly.md", "docs/05_fabrication_assembly.md"),
    ("СИМ-07", "Детали для лазера, раскрой труб (таблицы)", "docs/generated/fabrication_tables.md", "docs/generated/fabrication_tables.md, fabrication/*.csv"),
    ("СИМ-08", "Ведомость материалов и крепежа", "docs/generated/bom.md", "docs/generated/bom.md"),
    ("СИМ-09", "Результаты расчёта (МКЭ, крепёж)", "docs/generated/calc_results.md", "docs/generated/calc_results.md"),
    ("СИМ-10", "Чертежи, листы S01–S12", "drawings", "drawings/simrig_concept_drawings.pdf, drawings/*.png"),
    ("СИМ-11", "Файлы для лазерной резки DXF (Л01–Л29)", None, "fabrication/dxf/"),
    ("СИМ-12", "3D-модель: STEP AP214/AP242, STL", None, "out/step/, out/stl/"),
    ("СИМ-13", "Исходная параметрическая модель и расчёт", None, "cad/*.py, calc/frame_fem.py"),
    ("СИМ-14", "Протокол автоматических проверок модели", None, "out/interference_report.json"),
]


def full():
    story = [P("Регулируемая рама автосимулятора", "title"),
             P(f"Документация для изготовления · ревизия {REV} · {datetime.date.today():%d.%m.%Y}", "sub"),
             Spacer(1, 8)]
    story += img("drawings/3d/nominal.png", max_h=85 * mm)
    story.append(P("<b>Статус.</b> Комплект для изготовления <b>одного экземпляра</b>. Размеры в мм. "
                   "Пометки: <b>[П]</b> — предварительный параметр, <b>[!]</b> — требует проверки или уточнения "
                   "после выбора руля, педалей, сиденья. Отверстия под оборудование не проектировались "
                   "(сверлятся по месту). Сначала прочитайте «1_Кратко_о_раме.pdf».", "note"))
    story.append(P("<b>Проект не закончен:</b> до заказа резки нужно решить 4 вопроса (группа А в СИМ-01 — вариант сварки, ответы цеха, рулевая база, тип сиденья).", "warn"))
    story.append(P("Изменения ревизии 4 (последние)", "h2"))
    story += bullets(["Вкладыши телескопов — из обычного холоднокатаного листа 1,5 / 2,0 / 2,5 мм (вместо нержавейки).",
                      "Брусок 40×40: калиброванный желателен, допускается горячекатаный — зазор выбирается вкладышами.",
                      "Исправлены подписи в ведомости: лонжерон L=1400, площадка руля — лист 12 мм."])
    story.append(PageBreak())
    story.append(P("СИМ-00. Ведомость документов", "h1"))
    story.append(table([["Обозначение", "Наименование", "Файл / папка"]] +
                       [[a, b, d] for a, b, _, d in FULL_DOCS], widths=[0.13, 0.47, 0.40]))
    story.append(Spacer(1, 8))
    story.append(P("Как читать комплект", "h2"))
    story += bullets([
        "<b>Мастеру/сварщику:</b> СИМ-06 (порядок, допуски, карта сварки) → СИМ-07 (что резать) → листы S01–S04, "
        "S12 → DXF.",
        "<b>Лазерному цеху:</b> папка fabrication/dxf/ и таблица laser_parts.csv (позиция, толщина, количество). "
        "Слой CUT — резка, слой MARK — гравировка.",
        "<b>Трубы:</b> fabrication/cut_list.csv (длины, отверстия трубореза, углы реза подкосов).",
        "<b>Конструктору для проверки:</b> СИМ-02…05, СИМ-09, 3D-модель STEP, исходники cad/*.py.",
    ])
    story.append(PageBreak())
    for code, name, src, _ in FULL_DOCS:
        if not src or src == "drawings":
            continue
        story.append(P(f"{code}. {name}", "h1"))
        fl = md_flowables(src, shift=1)
        if fl and isinstance(fl[0], Paragraph) and fl[0].style.name in ("h2", "h1"):
            fl = fl[1:]            # заголовок файла заменён обозначением
        story += fl
        story.append(PageBreak())
    story.append(P("СИМ-10. Чертежи", "h1"))
    story.append(P("Листы S01–S12 (формат A3, горизонтально) следуют далее.", "p"))
    tmp = OUT_FULL + ".tmp.pdf"
    doc = make_doc(tmp, "Рама автосимулятора — документация для изготовления")
    doc.build(story, onFirstPage=footer("документация"), onLaterPages=footer("документация"))

    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for src in (tmp, os.path.join(ROOT, "drawings/simrig_concept_drawings.pdf")):
        for pg in PdfReader(src).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": "Рама автосимулятора — документация для изготовления"})
    with open(OUT_FULL, "wb") as f:
        w.write(f)
    os.remove(tmp)


if __name__ == "__main__":
    brief()
    full()
    for p in (OUT_BRIEF, OUT_FULL):
        print(os.path.relpath(p, ROOT), f"{os.path.getsize(p) / 1e6:.1f} МБ")
