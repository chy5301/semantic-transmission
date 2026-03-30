"""Gradio 主题定义与自定义 CSS。"""

import gradio as gr


def get_theme() -> gr.themes.Soft:
    """创建语义传输系统的 Gradio 主题。

    基于 Soft 主题，使用 Sky + Slate 配色方案。
    """
    return gr.themes.Soft(
        primary_hue="sky",
        neutral_hue="slate",
        font=[
            gr.themes.GoogleFont("Noto Sans SC"),
            "system-ui",
            "-apple-system",
            "sans-serif",
        ],
        font_mono=[
            "Cascadia Code",
            "JetBrains Mono",
            "Fira Code",
            "monospace",
        ],
    ).set(
        body_background_fill="#F8FAFC",
        block_background_fill="#FFFFFF",
        block_border_color="#E2E8F0",
        button_primary_background_fill="#0369A1",
        button_primary_text_color="#FFFFFF",
        input_background_fill="#FFFFFF",
        input_border_color="#E2E8F0",
    )


CUSTOM_CSS = """
/* 日志区使用等宽字体 */
.log-output textarea {
    font-family: "Cascadia Code", "JetBrains Mono", "Fira Code", monospace !important;
    font-size: 13px !important;
    line-height: 1.6 !important;
}

/* 统计数据表格紧凑化 */
.stats-table table {
    font-variant-numeric: tabular-nums;
}

/* 状态颜色 */
.status-text p {
    margin: 0;
    font-size: 14px;
}

/* 隐藏 Radio 组件的圆点指示器，选中项已有蓝色背景高亮 */
.mode-radio input[type="radio"] {
    display: none !important;
}

"""
