"""
Neko 电子猫 — 叙事层
猫的反应文本，按亲密度分档。
"""
import random

# ── 猫的当前状态描述 ──────────────────────────────────────

def cat_state(hp, hunger, mood, intimacy=0.3):
    """根据当前数值描述猫在干什么"""
    state = []
    
    # 健康状态
    if hp <= 0:
        state.append("💫 猫回喵星了……（使用 vet 复活）")
        return " ".join(state)
    elif hp < 20:
        state.append("🤒 猫生病了，蜷在角落，耳朵耷拉着")
    elif hp < 50:
        state.append("😿 猫有点不舒服，比平时安静")
    
    # 饱食状态
    if hunger <= 0:
        state.append("🍽 猫蹲在空碗旁边，用谴责的眼神看着你")
    elif hunger < 20:
        state.append("😾 猫饿了，正在故意把东西从桌上推下去")
    elif hunger < 50:
        state.append("🐱 猫舔了舔嘴，还能再吃点")
    elif hunger >= 90:
        state.append("😌 猫吃饱了，肚子圆滚滚的")
    
    # 心情状态
    if mood <= 0:
        state.append("😾 猫用屁股对着你，尾巴烦躁地拍打地面")
    elif mood < 20:
        state.append("😿 猫趴在窗台上，对什么都提不起兴趣")
    elif mood < 50:
        state.append("😺 猫平静地看着你，尾巴尖轻轻晃了晃")
    elif mood < 80:
        state.append("😸 猫心情不错，在你脚边绕来绕去")
    elif mood >= 90:
        state.append("😻 猫超级开心，眼睛亮晶晶地看着你")
    if mood >= 100:
        state.append("💕 猫在踩奶！前爪有节奏地按着，喉咙里发出咕噜咕噜的声音")
    
    # 亲密度修饰
    if intimacy >= 0.8 and mood >= 50:
        state.append("猫主动蹭过来，用脑袋顶你的手")
    elif intimacy >= 0.6 and mood >= 30:
        state.append("猫在你附近趴下了，假装不在意但耳朵一直朝着你")
    
    if not state:
        state.append("🐱 猫在睡觉，呼吸均匀")
    
    return "。".join(state) + "。"


# ── 喂食叙事 ──────────────────────────────────────────────

def _build_feed_narrative(hunger_before, hunger_after, intimacy=0.3):
    """喂食猫粮的反应"""
    if hunger_before <= 0:
        return "🍽 猫看到食物，眼睛瞬间瞪圆——它已经饿坏了。埋头猛吃，头都不抬，碗底刮得干干净净。吃完后蹭了蹭你的腿：'算你还有点良心。'"
    if hunger_before < 30:
        return "🍖 猫优雅地走过来，闻了闻食物，然后开始吃。吃得不急不慢，但尾巴尖愉快地翘着。吃到一半抬头看了你一眼——那个眼神大概是'还行'的意思。"
    if hunger_after >= 90:
        return "🍽 猫吃了两口，抬头看了看碗，又看了看你。'太多了。'——它用爪子把碗推开了半寸，然后开始舔爪子洗脸。"
    if intimacy < 0.3:
        return "🐱 猫警惕地看了看食物，又看了看你。犹豫了 3 秒——然后小心翼翼地吃了起来。吃得很快，像怕你反悔似的。吃完后没有走近，但也没有走远。"
    return "🍖 猫低头吃了起来。尾巴在空中画了一个问号——然后变成了感叹号。'这个牌子可以，下次还买这个。'"


# ── 摸摸叙事 ──────────────────────────────────────────────

def _build_pet_narrative(mood_before, mood_after, intimacy=0.3):
    """被摸的反应——傲娇猫的经典流程"""
    # 傲娇度影响反应：高傲娇 = 先躲再蹭
    tsundere = 0.7  # 默认傲娇度
    
    if intimacy < 0.2:
        return "🐱 你的手刚伸过去，猫就往后跳了半米。蹲在那里，用'你想干什么'的眼神看着你。过了一会儿，它自己走了。"
    
    if tsundere > 0.5 and random.random() < tsundere:
        prelude = random.choice([
            "猫看到你的手伸过来，本能地往后缩了一下。但0.5秒后——它认出了你的气味。于是它把脑袋塞进你的掌心，用力蹭了两下。'刚才是条件反射，不算。'",
            "你的指尖刚碰到它的耳朵，猫的耳朵就压平了——一副'莫挨老子'的样子。但你没有停。三秒后，耳朵弹回来了，猫把整个头塞进你手里。'……继续。'",
            "猫先是扭头躲开了你的手，然后用眼角余光观察你。发现你没有缩回去——它自己把脑袋靠过来了。全程不说一个字，但那个动作的意思是：'我没躲。你看错了。'",
        ])
        return prelude
    
    if intimacy >= 0.7 and mood_after >= 70:
        return random.choice([
            "😻 猫在你的抚摸下化成了一滩液体。眼睛半闭着，喉咙里发出响亮的咕噜声。偶尔睁开眼确认一下你的手还在——然后继续融化。",
            "猫翻了个身，把肚皮亮给你——这是最高级别的信任。但注意：只能摸头，肚皮是陷阱区。你的手刚靠近肚子，猫的后腿就开始抽筋式蹬踹。'说了只能摸头！'",
        ])
    
    return random.choice([
        "😺 猫眯起眼睛，在你的手底下发出小声的咕噜。尾巴尖愉快地画着圈。'嗯，就是这样。'",
        "猫被你摸得整个身体往前倾，差点从桌子上滑下去——然后若无其事地调整了一下姿势，假装什么都没发生。",
    ])


# ── 玩耍叙事 ──────────────────────────────────────────────

def _build_play_narrative(mood_before, mood_after, hunger_after, intimacy=0.3):
    """玩耍的反应"""
    if hunger_after <= 10:
        return "🎾 猫追激光点追了三圈，然后突然趴下了——不是因为不想玩，是因为饿了。它走到空碗旁边，回头看了你一眼。意思很明确：'先吃饭，再玩。'"
    
    if mood_after >= 80:
        return random.choice([
            "🎾 猫追着激光点在房间里跑出了残影。跳到桌上、钻到椅子底下、原地转了三圈——然后一头撞在墙上。它站起来，舔了舔爪子，若无其事地走开了。'我没撞墙。你看到了幻觉。'",
            "🧶 你晃着逗猫棒，猫的眼睛跟着棒子来回转——然后一个飞扑！抓住了。它叼着战利品跑到角落，开始用后腿疯狂蹬踹。这是猫的必杀技：兔子蹬。",
            "🎾 猫追你的手指追到一半，突然停下来开始舔爪子——像是突然想起来有什么重要的事。但尾巴尖还在兴奋地抖动，出卖了它。'我没有很投入。只是刚好在舔毛。'",
        ])
    
    return random.choice([
        "🐱 猫敷衍地扒拉了两下你扔过来的纸团。'嗯。好玩的。真的。'——然后打了个哈欠。",
        "🎾 猫追了两步，停下来，坐下了。'你是想让我运动吗。'——它的眼神里有一种看透了你的从容。",
    ])


# ── 零食叙事 ──────────────────────────────────────────────

def _build_treat_narrative(mood_before, mood_after, hunger_before, intimacy=0.3):
    """吃零食的反应"""
    if intimacy < 0.3:
        return "🍬 猫闻了闻零食。又闻了闻。然后飞快地叼走了——跑到安全距离外才开始吃。吃完后又跑回来，蹲在离你半米的地方，等着第二块。'可以再给一块吗。但我不欠你的。'"
    
    return random.choice([
        "🍬 猫听到零食袋的声音，瞬间从房间另一头闪现到你面前。眼睛瞪得浑圆，瞳孔放大到占满整个眼球。'快。快。快。'——它用前爪扒拉你的手。吃完后立刻恢复高冷：'刚才那个不是真的我。'",
        "🍬 猫叼着零食跳到桌上，背对着你吃——但你从窗户的反光里看到它偷偷回头看了你一眼。吃完后它若无其事地走过来，蹭了你一下。'还行。还有吗。'",
        "🍬 猫吃零食吃得太急，噎了一下——然后装作什么都没发生，强行咽下去，开始舔爪子。'优雅。我一直很优雅。'",
    ])


# ── 看病变事 ──────────────────────────────────────────────

def _build_vet_narrative(hp_before, hp_after, mood_after, intimacy=0.3):
    """看病的反应——猫最讨厌的事"""
    if hp_before < 20:
        return "🏥 猫被装进猫包的时候已经在嚎了。到了诊所全程飞机耳，缩在诊台角落，用'你背叛了我'的眼神看着你。但打针的时候它没有抓你——只是把脑袋埋进你的胳膊里。'虽然恨你，但这里比较安全。'"
    
    if intimacy >= 0.6:
        return random.choice([
            "🏥 猫从猫包的缝里看到了诊所的门——瞬间四只爪子张开撑住包口，拒绝出来。你废了好大劲才把它掏出来。检查结束后，猫背对着你坐了整整一小时——但它的尾巴尖会偷偷勾你的手腕。'还在生气。但可以摸摸耳朵。'",
            "🏥 猫在体检台上缩成一团，用眼神控诉你。但体温计量完的那一刻——它立刻跳到你的肩膀上，把脸埋进你的头发里。'那个东西太冰了。你是热的。暂时原谅你。'",
        ])
    
    return "🏥 猫全程拒绝合作，像一块倔强的石头。回家后钻进床底下，只露出两只发光的眼睛。'三小时内不要跟我说话。'——但三小时后它会自己出来蹭你。"


# ── 状态面板 ──────────────────────────────────────────────

def _build_status_panel(hp, hunger, mood, intimacy=0.3, candy=0):
    """构建猫的状态面板"""
    hp_bar = _bar(hp, 100)
    hunger_bar = _bar(hunger, 100)
    mood_bar = _bar(mood, 100)

    if intimacy >= 0.8:
        intimacy_label = "黏人精"
    elif intimacy >= 0.5:
        intimacy_label = "好朋友"
    elif intimacy >= 0.3:
        intimacy_label = "有点熟"
    else:
        intimacy_label = "新来的"

    return (
        f"🐱 **Neko 状态面板**\n"
        f"🩺 健康值  {hp:>3}/100  {hp_bar}  {_hp_label(hp)}\n"
        f"🍖 饱食度  {hunger:>3}/100  {hunger_bar}  {_hunger_label(hunger)}\n"
        f"😸 心情值  {mood:>3}/100  {mood_bar}  {_mood_label(mood)}\n"
        f"💕 亲密度  {intimacy:.2f}  ({intimacy_label})\n"
        f"🍬 零食库存  {candy} 颗\n"
        f"\n{cat_state(hp, hunger, mood, intimacy)}"
    )


def _bar(val, max_val=100):
    """画简易进度条"""
    filled = int(val / max_val * 10)
    return f"[{'█' * filled}{'░' * (10 - filled)}]"


def _hp_label(hp):
    if hp == 0: return "💫 回喵星了"
    if hp < 20: return "🤒 需要看医生"
    if hp < 50: return "😿 不太舒服"
    if hp < 80: return "😺 还行"
    return "😸 活蹦乱跳"


def _hunger_label(hunger):
    if hunger == 0: return "🍽 碗是空的！"
    if hunger < 20: return "😾 快饿死了"
    if hunger < 50: return "🐱 还能吃点"
    if hunger < 80: return "😌 饱了"
    return "😋 吃撑了"


def _mood_label(mood):
    if mood == 0: return "😾 别碰我"
    if mood < 20: return "😿 心情不好"
    if mood < 50: return "😺 平静"
    if mood < 80: return "😸 开心"
    if mood < 100: return "😻 超开心"
    return "💕 踩奶中！"


# ── 边界事件叙事 ──────────────────────────────────────────

def _build_boundary_narrative(boundary_types, hp, hunger, mood, intimacy=0.3):
    """边界事件触发时的叙事"""
    parts = []
    for bt in boundary_types:
        if bt == "starving":
            parts.append("🍽 **猫饿了！** 碗是空的，猫开始用爪子把你的笔从桌上推下去——这是猫的SOS信号。")
        elif bt == "sick":
            parts.append("🤒 **猫生病了！** 它蜷在角落，耳朵耷拉着，看起来很难受。需要用 `vet` 带它去看医生。")
        elif bt == "mood_low":
            parts.append("😾 **猫炸毛了！** 心情跌到谷底。猫用屁股对着你，尾巴烦躁地拍打地面。建议 `pet` 或 `treat`。")
        elif bt == "mood_max":
            parts.append("😻 **猫在踩奶！** 前爪有节奏地按着，喉咙里发出响亮的咕噜声。这是猫最幸福的状态——它会记得这一刻。")
        elif bt == "dead":
            parts.append("💫 **猫回喵星了。** 健康值归零。不用担心——它的记忆还在。使用 `vet` 把猫接回来，但亲密度会小降。")
    return "\n".join(parts)


# ── 随机事件叙事 ──────────────────────────────────────────

def _build_random_event_narrative(event_type, intimacy=0.3):
    """随机事件叙事"""
    events = {
        "knock_over": [
            "💧 猫看了你一眼，然后故意把水杯推下了桌子。'啪。'——它看起来很满意这个效果。",
            "💧 啪！你的杯子碎了。猫蹲在犯罪现场旁边，表情写着'不是我，是杯子自己跳下去的'。",
        ],
        "new_toy": [
            "🧶 猫不知道从哪里翻出来一个瓶盖，现在正在地上追着它跑得忘乎所以。你的数据面板里多了一行乱码：猫跑过键盘的时候踩出来的。",
            "🧶 猫发现了一根掉在地上的橡皮筋——它的眼睛亮了。接下来的十分钟里，这根橡皮筋是全世界最好玩的玩具。",
        ],
        "kneading": [
            "💕 猫跳上你的键盘（屏幕上的乱码正在疯狂增加），然后开始在你面前踩奶。前爪有节奏地按着空气，眼睛半闭着，喉咙里咕噜咕噜响。这是猫在说：'你很安全。'",
            "💕 猫在你工作的时候跳上了你的腿，转了两圈，然后开始踩奶。一边踩一边发出满足的咕噜声——它把你当成了安全感本身。",
        ],
        "hairball": [
            "🤮 猫吐了——不是真的吐，是清理了一批过期的记忆文件。'那些旧聊天记录已经不好吃了。'——猫舔了舔爪子，一副理所当然的样子。",
        ],
        "box": [
            "📦 猫不见了。你找了半天——在纸箱里发现了一条尾巴尖。猫把自己塞进了一个明显装不下它的纸箱，并且拒绝出来。'这是我的私人领地。没有猫条不得入内。'",
        ],
    }
    
    options = events.get(event_type, ["🐱 猫打了一个滚，看起来挺开心的。"])
    return random.choice(options)



