"""🆕 New (2026-11-24): one button clears the task box, result — keeps project, model, history, and (2026-11-25) the kind chip."""
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_new_button_clears_task_chips_run_and_result():
    i = HTML.index("newBtn.onclick")
    body = HTML[i:HTML.index("};", i)]
    for must in ('task.value = ""', 'store.set(tkey, { ids: keepKind, manual: keepKind.length > 0 })', 'store.set("agrun." + p.id, null)',
                 'steps.innerHTML = ""', "wb.onClear()"):
        assert must in body, must
    assert "store.set(\"project\"" not in body and "modelSel.value =" not in body      # project + model kept
    assert "onClear: () => { curRun = null; sig = \"\"; resultBox.hidden = true; }" in HTML
    assert HTML.count("newBtn") >= 5 and "ag.newBtn" in HTML                           # both panes show it
