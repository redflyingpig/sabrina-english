"""Original, deterministic sentence frames for generated lesson content."""

from __future__ import annotations

from typing import Dict, List, Tuple


TOPIC_LABELS = {
    "daily-life": "日常生活",
    "family": "家庭",
    "school": "学校",
    "work": "工作",
    "shopping": "购物",
    "food": "饮食",
    "health": "健康",
    "transport": "交通",
    "travel": "旅行",
    "weather": "天气",
    "home": "居家",
    "relationships": "人际交往",
    "entertainment": "娱乐",
    "digital-life": "数字生活",
    "public-services": "公共服务",
    "time": "时间安排",
    "nature": "自然",
}

TOPIC_EXAMPLE_LABELS = {
    "daily-life": "an everyday conversation",
    "family": "a family conversation",
    "school": "a school conversation",
    "work": "a work conversation",
    "shopping": "a shopping conversation",
    "food": "a conversation about food",
    "health": "a conversation about health",
    "transport": "a conversation about transport",
    "travel": "a travel conversation",
    "weather": "a conversation about the weather",
    "home": "a conversation at home",
    "relationships": "a conversation with friends",
    "entertainment": "a conversation about entertainment",
    "digital-life": "a conversation about digital life",
    "public-services": "a conversation about public services",
    "time": "a conversation about schedules",
    "nature": "a conversation about nature",
}


def build_example(row: Dict[str, str], topic: str) -> str:
    """Create an original, sense-neutral learning sentence."""
    word = row["word"].strip()
    context = TOPIC_EXAMPLE_LABELS.get(topic, TOPIC_EXAMPLE_LABELS["daily-life"])
    return f'I wrote down the word “{word}” after hearing it in {context}.'


EXPRESSION_ITEMS: List[Tuple[str, str]] = [
    ("the bus schedule", "transport"),
    ("my appointment", "health"),
    ("the shopping list", "shopping"),
    ("today's homework", "school"),
    ("the meeting time", "work"),
    ("our dinner plan", "food"),
    ("the weather forecast", "weather"),
    ("the hotel booking", "travel"),
    ("the front door", "home"),
    ("the family calendar", "family"),
    ("the train platform", "transport"),
    ("the medicine label", "health"),
    ("the final price", "shopping"),
    ("the class project", "school"),
    ("the office report", "work"),
    ("the lunch order", "food"),
    ("tomorrow's temperature", "weather"),
    ("the return flight", "travel"),
    ("the kitchen light", "home"),
    ("our weekend visit", "relationships"),
    ("the film tickets", "entertainment"),
    ("the Wi-Fi password", "digital-life"),
    ("the library card", "public-services"),
    ("the starting time", "time"),
    ("the park entrance", "nature"),
    ("the taxi address", "transport"),
    ("the doctor's advice", "health"),
    ("the receipt", "shopping"),
    ("the lesson notes", "school"),
    ("the delivery date", "daily-life"),
]


EXPRESSION_FRAMES: List[Tuple[str, str, str, str]] = [
    ("Could you check {item}?", "请对方核对信息。", "Could you check {item}? I want to make sure it is correct.", "A2"),
    ("Can you help me with {item}?", "礼貌请求帮助。", "Can you help me with {item}? I am not sure what to do.", "A1"),
    ("I need to check {item}.", "说明需要核对某事。", "I need to check {item} before we leave.", "A1"),
    ("Let's talk about {item}.", "提议讨论某件事。", "Let's talk about {item} when everyone is here.", "A1"),
    ("What do you think about {item}?", "询问对方的看法。", "What do you think about {item}? Your opinion matters.", "A2"),
    ("Do you know about {item}?", "询问对方是否了解某事。", "Do you know about {item}? I heard something changed.", "A1"),
    ("Please remember {item}.", "提醒对方记住某事。", "Please remember {item} before you go out.", "A1"),
    ("I forgot about {item}.", "说明自己忘了某事。", "I forgot about {item}, so I need to check it now.", "A2"),
    ("We should discuss {item}.", "建议一起讨论某事。", "We should discuss {item} before making a decision.", "B1"),
    ("I'm worried about {item}.", "表达对某事的担心。", "I'm worried about {item}. Could we check it again?", "A2"),
    ("I'm ready for {item}.", "表示已为某事做好准备。", "I'm ready for {item}. We can start whenever you like.", "A1"),
    ("Are you ready for {item}?", "询问对方是否准备好。", "Are you ready for {item}? We need to leave soon.", "A1"),
    ("Thanks for helping with {item}.", "感谢对方帮忙处理某事。", "Thanks for helping with {item}. It saved me a lot of time.", "A2"),
    ("Could we change {item}?", "礼貌询问能否更改某事。", "Could we change {item}? The current plan is difficult for me.", "B1"),
    ("Let's confirm {item}.", "提议确认信息。", "Let's confirm {item} before we tell everyone.", "A2"),
    ("I have a question about {item}.", "引出关于某事的问题。", "I have a question about {item}. Could you explain it?", "A2"),
    ("There is a problem with {item}.", "说明某事出现问题。", "There is a problem with {item}, but we can solve it.", "A2"),
    ("Everything is ready for {item}.", "表示某事所需准备已经完成。", "Everything is ready for {item}. We can begin now.", "B1"),
    ("We have enough time for {item}.", "表示时间足够。", "We have enough time for {item}, so there is no need to hurry.", "B1"),
    ("Can we decide on {item}?", "提议就某事作出决定。", "Can we decide on {item} before the end of the day?", "B1"),
]


PATTERN_BASES: List[Tuple[str, str, str, str]] = [
    ("I need to + verb {context}", "表达需要做某事。", "I need to check the details {example_context}.", "A1"),
    ("I want to + verb {context}", "表达想做某事。", "I want to practise English {example_context}.", "A1"),
    ("I plan to + verb {context}", "表达计划做某事。", "I plan to finish the task {example_context}.", "A2"),
    ("I hope to + verb {context}", "表达希望做某事。", "I hope to see you {example_context}.", "A2"),
    ("I forgot to + verb {context}", "表达忘记做某事。", "I forgot to send the message {example_context}.", "A2"),
    ("I remembered to + verb {context}", "表达记得做了某事。", "I remembered to bring my card {example_context}.", "A2"),
    ("I usually + verb {context}", "描述通常的习惯。", "I usually take a short walk {example_context}.", "A1"),
    ("I rarely + verb {context}", "描述很少发生的习惯。", "I rarely eat out {example_context}.", "A2"),
    ("I have already + past participle {context}", "说明某事已经完成。", "I have already finished the report {example_context}.", "B1"),
    ("I haven't + past participle + yet {context}", "说明某事尚未完成。", "I haven't booked the tickets yet {example_context}.", "B1"),
    ("Could you + verb {context}?", "礼貌请求对方做某事。", "Could you speak more slowly {example_context}?", "A2"),
    ("Would you like to + verb {context}?", "礼貌邀请对方做某事。", "Would you like to join us {example_context}?", "A2"),
    ("Do you mind + verb-ing {context}?", "礼貌询问对方是否介意。", "Do you mind waiting here {example_context}?", "B1"),
    ("How often do you + verb {context}?", "询问做某事的频率。", "How often do you exercise {example_context}?", "A2"),
    ("How long does it take to + verb {context}?", "询问做某事需要多久。", "How long does it take to get there {example_context}?", "A2"),
    ("There is a + noun {context}", "说明某处有一个事物。", "There is a small shop nearby {example_context}.", "A1"),
    ("There are + plural noun {context}", "说明某处有多个事物。", "There are several seats available {example_context}.", "A1"),
    ("It is important to + verb {context}", "强调做某事很重要。", "It is important to listen carefully {example_context}.", "B1"),
    ("It is easy to + verb {context}", "说明做某事容易。", "It is easy to find the station {example_context}.", "A2"),
    ("It is difficult to + verb {context}", "说明做某事困难。", "It is difficult to concentrate {example_context}.", "A2"),
    ("If + present, will + verb {context}", "表达可能发生的条件和结果。", "If it rains, we will stay inside {example_context}.", "B1"),
    ("When + present, + present {context}", "描述规律或习惯。", "When I feel tired, I take a break {example_context}.", "A2"),
    ("Because + clause, + clause {context}", "说明原因。", "Because the bus was late, I walked {example_context}.", "A2"),
    ("Although + clause, + clause {context}", "表达让步关系。", "Although it was raining, we went out {example_context}.", "B1"),
    ("The more + clause, the more + clause {context}", "表达两个变化之间的关系。", "The more I practise, the more confident I feel {example_context}.", "B2"),
]


PATTERN_CONTEXTS: List[Tuple[str, str, str]] = [
    ("at home", "at home", "home"),
    ("at work", "at work", "work"),
    ("at school", "at school", "school"),
    ("before breakfast", "before breakfast", "food"),
    ("after dinner", "after dinner", "food"),
    ("on weekdays", "on weekdays", "time"),
    ("at the weekend", "at the weekend", "entertainment"),
    ("when travelling", "when we travel", "travel"),
    ("in bad weather", "when the weather is bad", "weather"),
    ("with friends", "with my friends", "relationships"),
]
