from carenav.agents.benefits import normalize_service


def test_lab_tests_normalize_to_lab_panel_category():
    assert normalize_service("is ca-125 test covered") == "lab_panel"
    assert normalize_service("blood work") == "lab_panel"
