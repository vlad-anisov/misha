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
    ("pedals", "Педальный узел"), ("seat", "Узел сиденья"), ("side", "Кронштейн шифтера / ручника"),
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
            if gg != g or kind in ("fastener", "purchased"):
                continue
            mass = r["vol"] * 7.85e-6 if kind == "steel" else r["vol"] * 1.0e-6
            tot += mass if kind == "steel" else 0
            L.append(f"| {', '.join(sorted(r['names']))} | {spec} | {r['n']} | {mass:.2f} |")
        L.append("")
    L += ["## Крепёж и покупные изделия", "", "| Изделие | Кол-во в модели | Где |", "|---|---|---|"]
    fast = OrderedDict()
    for (gg, kind, spec), r in rows.items():
        if kind not in ("fastener", "purchased"):
            continue
        f = fast.setdefault(spec, dict(n=0, where=set()))
        f["n"] += r["n"]
        f["where"].add(GROUPS.get(gg, gg))
    for spec, f in fast.items():
        L.append(f"| {spec} | {f['n']} | {'; '.join(sorted(f['where']))} |")
    L += ["", f"**Итого сталь по модели ≈ {tot:.0f} кг** (без крепежа).", "",
          "### Рекомендуемый запас и уточнения по крепежу",
          "* Болты регулировок: ISO 4014 (с гладкой частью стержня в плоскости среза), класс 8.8, оцинк., М12×40, М12×45 и М12×90. "
          "Запас +20 %.",
          "* Гайки — ISO 7042 (цельнометаллические самоконтрящиеся) + шайбы ISO 7089 под головку и гайку; "
          "затяжка 80 Н·м; по желанию фиксатор резьбы средней прочности.",
          "* Широкие шайбы DIN 9021 / ISO 7093 — под гайки на стенках труб 3 мм (стойки руля, стакан шифтера).",
          "* Регулируемые опоры: М12×80, шарнирные, Ø50–60, ≥ 300 кг каждая; контргайка сверху пластины.",
          "* Вкладыши телескопов: лазер из листа 2 мм + запасной комплект 1.5 и 2.5 мм для подбора зазора.",
          "* Приварных гаек в регулировках нет: везде сквозные болты с гайками ISO 7042 (кроме 6 гаек М12 под опоры).",
          ]
    os.makedirs(os.path.join(ROOT, "docs", "generated"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "generated", "bom.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
