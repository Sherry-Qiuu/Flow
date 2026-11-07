"""Seven-phase decomposition templates.

Templates are product copy in Chinese; code comments and identifiers are
in English. Every phase starts with an action verb and has a measurable
completion criterion.
"""

from __future__ import annotations

from dataclasses import dataclass

from planner.models import Category


@dataclass(frozen=True)
class StepTemplate:
    title: str
    criteria: str
    difficulty: int = 2


TEMPLATES: dict[Category, tuple[StepTemplate, ...]] = {
    Category.WRITING: (
        StepTemplate(
            "打开文档，列出 3 个核心论点",
            "文档中写下 3 条可以展开的论点",
            2,
        ),
        StepTemplate(
            "收集每个论点的 2 条证据或用例",
            "每个论点都有至少 2 条支撑材料",
            3,
        ),
        StepTemplate(
            "写出引言，交代背景与全文结构",
            "引言完成并给出全文结构",
            2,
        ),
        StepTemplate(
            "完成第一个主体段落初稿",
            "第一个论点段落有完整初稿",
            3,
        ),
        StepTemplate(
            "完成其余主体段落初稿",
            "其余论点段落都有初稿",
            3,
        ),
        StepTemplate(
            "写出结论并回扣 3 个论点",
            "结论回应全部论点，没有新观点",
            2,
        ),
        StepTemplate(
            "通读全文，统一术语并润色",
            "全文无占位符，语句通顺",
            1,
        ),
    ),
    Category.READING: (
        StepTemplate(
            "翻看目录和标题，标出 3 个要解决的问题",
            "写下 3 个阅读问题",
            1,
        ),
        StepTemplate(
            "通读第一节，划出关键定义",
            "第一节的关键定义都有标注",
            2,
        ),
        StepTemplate(
            "读完剩余章节，记录每节一句话摘要",
            "每节都有一句话摘要",
            2,
        ),
        StepTemplate(
            "整理概念图或笔记框架",
            "形成一张概念图或一页笔记",
            2,
        ),
        StepTemplate(
            "回看标注，复述核心论证",
            "不看原文能复述 3 条核心论证",
            1,
        ),
        StepTemplate(
            "做 5 道自测题并订正",
            "5 道题完成且错题有订正",
            2,
        ),
        StepTemplate(
            "写出 3 条可用于作业的要点",
            "3 条要点可直接引用到作业",
            1,
        ),
    ),
    Category.MEMORIZATION: (
        StepTemplate(
            "拆分要背的内容为 3 组，每组不超过 7 项",
            "材料被分成 3 组且每组不超过 7 项",
            1,
        ),
        StepTemplate(
            "朗读第一组 3 遍，遮住关键词复述",
            "第一组能脱离材料复述",
            2,
        ),
        StepTemplate(
            "编一个首字母故事记忆第二组",
            "第二组有一个可复述的记忆线索",
            2,
        ),
        StepTemplate(
            "默写前两组，标出卡壳处",
            "默写完成并标出所有卡壳点",
            2,
        ),
        StepTemplate(
            "重做卡壳处的 2 轮间隔回忆",
            "每个卡壳点都能间隔回忆成功",
            2,
        ),
        StepTemplate(
            "背诵第三组并串联全部内容",
            "三组内容能按顺序串联",
            2,
        ),
        StepTemplate(
            "复述全部内容，不看材料",
            "完整复述一遍且错误不超过 2 处",
            1,
        ),
    ),
    Category.EXPERIMENT: (
        StepTemplate(
            "阅读实验要求，列出变量和测量项",
            "变量表和测量项清单完成",
            2,
        ),
        StepTemplate(
            "准备器材并检查安全事项",
            "器材齐全，安全检查通过",
            1,
        ),
        StepTemplate(
            "搭建实验装置，试跑一次",
            "装置搭建完成并成功试跑",
            3,
        ),
        StepTemplate(
            "完成第一组数据采集并记录",
            "第一组数据完整记录",
            3,
        ),
        StepTemplate(
            "完成剩余组数据采集",
            "全部实验组数据记录完整",
            3,
        ),
        StepTemplate(
            "整理数据表并画图",
            "数据表完成并有一张结果图",
            2,
        ),
        StepTemplate(
            "写出误差分析与结论",
            "误差来源和结论各有 1 段说明",
            2,
        ),
    ),
    Category.DISCUSSION: (
        StepTemplate(
            "写下讨论目标和 3 个待决问题",
            "目标和 3 个问题写在同一页",
            1,
        ),
        StepTemplate(
            "收集组员观点并分类",
            "所有组员观点进入分类表",
            1,
        ),
        StepTemplate(
            "列出共识与分歧清单",
            "共识和分歧各有明确清单",
            2,
        ),
        StepTemplate(
            "准备每个分歧的一条论据",
            "每个分歧都有至少 1 条论据",
            2,
        ),
        StepTemplate(
            "形成讨论提纲并分配发言",
            "提纲完成且每人有发言位置",
            2,
        ),
        StepTemplate(
            "模拟演练一次，记录超时点",
            "完整演练一次并标出超时点",
            1,
        ),
        StepTemplate(
            "整理结论并发出会议纪要",
            "结论和行动项发给全部组员",
            1,
        ),
    ),
    Category.CODING: (
        StepTemplate(
            "阅读需求，写出 3 条验收标准",
            "3 条验收标准可被测试验证",
            2,
        ),
        StepTemplate(
            "画出模块草图并标出接口",
            "模块边界和接口签名明确",
            3,
        ),
        StepTemplate(
            "搭好项目骨架，跑通空实现",
            "项目能启动且测试命令可运行",
            2,
        ),
        StepTemplate(
            "实现核心逻辑并写一个单元测试",
            "核心用例通过且测试可重复",
            3,
        ),
        StepTemplate(
            "补齐边界情况与错误处理",
            "边界用例和错误路径都有覆盖",
            3,
        ),
        StepTemplate(
            "运行测试并修复失败项",
            "全部测试通过",
            2,
        ),
        StepTemplate(
            "整理提交说明和待办",
            "提交说明完成，遗留项有记录",
            1,
        ),
    ),
    Category.GENERAL: (
        StepTemplate(
            "拆解《{task}》，写下 3 个完成要点",
            "3 个完成要点写在纸上或文档里",
            1,
        ),
        StepTemplate(
            "收集所需资料和工具",
            "开始前需要的东西全部就位",
            1,
        ),
        StepTemplate(
            "完成第一个可交付的小块",
            "第一小块可以被看见或检查",
            2,
        ),
        StepTemplate(
            "继续推进主体部分",
            "主体部分完成一半以上",
            2,
        ),
        StepTemplate(
            "检查遗漏并补齐细节",
            "对照 3 个完成要点无遗漏",
            2,
        ),
        StepTemplate(
            "安排一次他检或自测",
            "获得一次外部反馈或自测结果",
            1,
        ),
        StepTemplate(
            "整理成果并记录下一步",
            "成果归档，下一步写清楚",
            1,
        ),
    ),
}
