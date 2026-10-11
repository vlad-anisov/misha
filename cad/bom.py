"""
Предварительная ведомость материалов и крепежа, собранная из модели.
НЕ является производственной спецификацией (см. шапку генерируемого файла).

    python cad/bom.py  ->  docs/generated/bom.md
"""
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from params import Config  # noqa: E402
from simrig import build_model  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GROUPS = OrderedDict([
    ("base", "Основание"), ("tower_fixed", "Рулевые стойки (неподвижная часть)"),
    ("height", "Узел высоты (подвижный П-узел) и сёдла"), ("deck", "Площадка руля"),
    ("pedals", "Педальный узел"), ("seat", "Узел сиденья"),
])


def main():
    m = build_model(Config(), refs=False)
    rows = OrderedDict()
    for p in m.parts:
        key = (p.group, p.kind, p.spec)
        r = rows.setdefault(key, dict(n=0, vol=0.0, names=set()))
        r["n"] += 1
        r["vol"] += p.shape.Volume()
        base = p.name.rsplit("_", 1)[0] if p.name[-2:] in ("_R", "_L") else p.name
        r["names"].add(base.rstrip("0123456789").rstrip("_"))
    L = ["# Предварительная ведомость материалов и крепежа (генерируется cad/bom.py)", "",
         "> **Не производственная спецификация.** Количества и сечения сняты с концептуальной модели "
         "(номинальная конфигурация). Длины — по модели без припусков на рез; трубы показаны без радиусов "
         "скругления углов. Перед заказом: проверить сортамент поставщика, добавить 10–15 % на рез и брак, "
         "уточнить крепёж после выбора руля, педалей и сиденья (их крепёж здесь НЕ учтён).", ""]
    tot = 0.0
    for g, gname in GROUPS.items():
        L += [f"## {gname}", "", "| Позиция (по модели) | Материал / изделие | Кол-во | Масса, кг (≈) |", "|---|---|---|---|"]
        for (gg, kind, spec), r in rows.items():
            if gg != g or kind == "fastener":
                continue
            mass = r["vol"] * 7.85e-6 if kind == "steel" else r["vol"] * 1.0e-6
            tot += mass if kind == "steel" else 0
            L.append(f"| {', '.join(sorted(r['names']))} | {spec} | {r['n']} | {mass:.2f} |")
        L.append("")
    L += ["## Крепёж и покупные изделия", "", "| Изделие | Кол-во в модели | Где |", "|---|---|---|"]
    fast = OrderedDict()
    for (gg, kind, spec), r in rows.items():
        if kind != "fastener":
            continue
        f = fast.setdefault(spec, dict(n=0, where=set()))
        f["n"] += r["n"]
        f["where"].add(GROUPS.get(gg, gg))
    for spec, f in fast.items():
        L.append(f"| {spec} | {f['n']} | {'; '.join(sorted(f['where']))} |")
    L += ["", f"**Итого сталь по модели ≈ {tot:.0f} кг** (без крепежа).", "",
          "### Рекомендуемый запас и уточнения по крепежу",
          "* Болты регулировок: ISO 4014 (с гладкой частью стержня в плоскости среза), класс 8.8, оцинк. — "
          "предварительно М12; длины уточнить по факту толщин после сборки. Запас +20 %.",
          "* Под головку — стопорные клиновые шайбы-пары (Nord-Lock NL12 или аналог) или шайба ISO 7089-300HV + "
          "резьбовой фиксатор средней прочности; в соединениях с обычной гайкой — гайка ISO 7042 (цельнометаллическая "
          "самоконтрящаяся) или ISO 7040 (с полиамидным кольцом, заменять после 5–10 перестановок).",
          "* Широкие шайбы DIN 9021 / ISO 7093 — где болт опирается на стенку трубы без накладки (в данной концепции "
          "таких несущих мест нет; держать в комплекте для адаптеров).",
          "* Гайки приварные DIN 929 М12 — проверить по паспорту класс прочности; если ниже 8 — снизить момент "
          "затяжки до 40–45 Н·м или применить гайки класса 8 высотой ≥ 0.8d.",
          "* Регулируемые опоры: М12, шарнирные, Ø50–60, допускаемая нагрузка ≥ 300 кг каждая.",
          "* Вкладыши: сталь холоднокатаная 2.0 мм (набор 1.6 / 1.8 / 2.0 / 2.2 для подбора), PA6 или UHMW-PE 2 мм.",
          ]
    os.makedirs(os.path.join(ROOT, "docs", "generated"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "generated", "bom.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
