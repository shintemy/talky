from talky.text_guard import (
    collapse_duplicate_output,
    enforce_pronoun_consistency,
    enforce_source_boundaries,
)


def test_enforce_pronoun_consistency_my_to_your() -> None:
    source = "\u80fd\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"
    output = "\u80fd\u542c\u5230\u60a8\u7684\u58f0\u97f3\u5417\uff1f"

    corrected = enforce_pronoun_consistency(source, output)

    assert corrected == "\u80fd\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"


def test_enforce_pronoun_consistency_preserve_you() -> None:
    source = "\u4f60\u53ef\u4ee5\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"
    output = "\u60a8\u53ef\u4ee5\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"

    corrected = enforce_pronoun_consistency(source, output)

    assert "\u4f60\u53ef\u4ee5" in corrected


def test_enforce_pronoun_consistency_you_not_to_me() -> None:
    source = "\u4f60\u6765\u64cd\u4f5c"
    output = "\u6211\u6765\u64cd\u4f5c"

    corrected = enforce_pronoun_consistency(source, output)

    assert corrected == "\u4f60\u6765\u64cd\u4f5c"


def test_collapse_duplicate_output_repeated_lines() -> None:
    text = "Do you hear the people sing?\nDo you hear the people sing?\n"

    collapsed = collapse_duplicate_output(text)

    assert collapsed == "Do you hear the people sing?"


def test_enforce_source_boundaries_blocks_introduced_advice() -> None:
    source = "明天上线发布功能，检查接口和文档。"
    output = "建议你先做灰度发布，再加回滚方案和沟通清单。"

    corrected = enforce_source_boundaries(source, output)

    assert corrected == source


def test_enforce_source_boundaries_keeps_faithful_rewrite() -> None:
    source = "明天上线发布功能，检查接口和文档。"
    output = "明天上线发布该功能，并检查接口与文档。"

    corrected = enforce_source_boundaries(source, output)

    assert corrected == output


def test_enforce_source_boundaries_preserves_question_intent() -> None:
    source = "How is everything?"
    output = "Everything is great."

    corrected = enforce_source_boundaries(source, output)

    assert corrected == source


def test_enforce_source_boundaries_blocks_question_to_markdown_outline() -> None:
    source = "如何检测每次开启服务时它是否有去检查版本更新？"
    output = (
        "### 检测服务启动时的更新行为\n\n"
        "- 观察启动日志，查看是否输出检查更新提示。\n"
        "- 分析代码逻辑，确认是否调用更新接口。\n"
        "- 验证网络请求，监测是否访问更新服务。"
    )

    corrected = enforce_source_boundaries(source, output)

    assert corrected == source
