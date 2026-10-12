"""Conservative Chinese date parser. Inputs must be mock data for this pilot."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from calendar import monthrange
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Australia/Melbourne')

@dataclass(frozen=True)
class Rules:
    # Inclusive day ranges. Defaults are proposals, not enabled production rules.
    periods: dict = field(default_factory=lambda: {'初': (1, 10), '中旬': (11, 20), '底': (21, 31), '末': (21, 31)})
    reminder_at: str = 'start'  # start / end
    weekdays_only: bool = False


def parse(text: str, *, anchor: date | datetime | None, today: date, rules: Rules | None = None) -> dict:
    """Anchor is the date the note was made, NOT the daily scan date.

    Only one leading time phrase is recognized. Reasons/actions remain original
    text; no guessed semantic facts, years, or event dates are generated.
    """
    rules = rules or Rules()
    if rules.reminder_at not in ('start', 'end'):
        raise ValueError('invalid reminder policy')
    for lo, hi in rules.periods.values():
        if not (1 <= lo <= hi <= 31):
            raise ValueError('invalid period range')
    if isinstance(anchor, datetime):
        if anchor.tzinfo is None:
            raise ValueError('anchor datetime must include timezone')
        anchor = anchor.astimezone(ZONE).date()
    if isinstance(today, datetime):
        if today.tzinfo is None:
            raise ValueError('today datetime must include timezone')
        today = today.astimezone(ZONE).date()
    out = dict(original_text=text, status='needs_confirmation', kind='unknown',
               window_start=None, window_end=None, proposed_reminder_date=None,
               can_remind=False, time_phrase=None, action_text=None,
               reason='无法可靠识别，请确认', timezone=ZONE.key,
               anchor_date=anchor.isoformat() if anchor else None)
    if not text.strip():
        out['reason'] = '内容为空'
        return out
    # Clauses are separated conservatively; never silently ignore a second time.
    parts = re.split(r'[，,。；;\n]', text.strip(), maxsplit=1)
    phrase = parts[0].strip()
    action = parts[1].strip() if len(parts) > 1 else ''
    out.update(time_phrase=phrase, action_text=action)
    event_words = r'回台湾|回国|回来|申请.*(?:结果|完成)|等.*(?:后|再)|之后|完成后|批准后|如果|届时'
    if re.search(event_words, text):
        out.update(kind='event', reason='存在事件条件；未确认事件发生，不生成日期')
        return out
    if re.search(r'\d{1,4}[-/]\d|\d+月|明年|今年|下周|本周|周[一二三四五六日天]|明天|今天|后天|\d+天后', action):
        out['reason'] = '正文还有时间表达，需确认哪个时间控制提醒'
        return out
    start = end = None
    kind = 'exact'
    explicit = re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', phrase)
    chinese = re.fullmatch(r'(?:(\d{4})年|(今年|明年))?(\d{1,2})月(?:(\d{1,2})[日号]|(初|中旬|底|末))?', phrase)
    try:
        if explicit:
            start = end = date(*map(int, explicit.groups()))
        elif chinese:
            year, relative_year, month, day, period = chinese.groups()
            if year:
                year = int(year)
            elif relative_year and anchor:
                year = anchor.year + (relative_year == '明年')
            else:
                out.update(kind='year_ambiguous', reason='缺少年份或记录时间，不能自动推断年份')
                return out
            month = int(month)
            last = monthrange(year, month)[1]
            if day:
                start = end = date(year, month, int(day))
            else:
                kind = 'fuzzy'
                lo, hi = rules.periods[period] if period else (1, last)
                if lo > last:
                    raise ValueError('period starts beyond month')
                start, end = date(year, month, lo), date(year, month, min(hi, last))
        elif re.fullmatch(r'(下周|本周)[一二三四五六日天]', phrase):
            if anchor is None:
                out['reason'] = '相对时间需要原始记录日期'
                return out
            day_number = '一二三四五六日'.find(phrase[-1].replace('天', '日'))
            monday = anchor - timedelta(days=anchor.weekday())
            start = end = monday + timedelta(days=day_number + (7 if phrase.startswith('下周') else 0))
            kind = 'relative'
        elif phrase in ('今天', '明天', '后天') or re.fullmatch(r'\d+天后', phrase):
            if anchor is None:
                out['reason'] = '相对时间需要原始记录日期'
                return out
            days = {'今天': 0, '明天': 1, '后天': 2}.get(phrase)
            if days is None:
                days = int(phrase[:-2])
                if days > 366:
                    out['reason'] = '相对间隔过长，需确认'
                    return out
            start = end = anchor + timedelta(days=days)
            kind = 'relative'
        else:
            return out
    except (ValueError, KeyError):
        out['reason'] = '日期不存在或规则未配置'
        return out
    reminder = start if rules.reminder_at == 'start' else end
    if rules.weekdays_only:
        while reminder.weekday() >= 5:
            reminder += timedelta(days=1)
    out.update(kind=kind, window_start=start.isoformat(), window_end=end.isoformat(),
               proposed_reminder_date=reminder.isoformat())
    if rules.weekdays_only and reminder > end:
        out['reason'] = '移到工作日将超出原时间窗口，请确认'
    elif end < today:
        out.update(status='overdue_review', reason='时间窗口已经过去；不自动改为明年或补发')
    else:
        out.update(status='proposed', reason='候选时间已生成，仍需人工确认；模糊时间策略也需批准')
    return out


def reminder_ready(result: dict, *, today: date, confirmed: bool,
                   current_text: str, event_satisfied: bool = False) -> bool:
    """A candidate never schedules itself. Events need a new confirmed date."""
    if not confirmed or result['original_text'] != current_text:
        return False
    if result['status'] != 'proposed' or not result['proposed_reminder_date']:
        return False
    return result['proposed_reminder_date'] <= today.isoformat() <= result['window_end']
