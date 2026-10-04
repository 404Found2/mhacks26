import json
import os
import re
import urllib.error
import urllib.request

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
DEFAULT_MODEL = 'openrouter/free'

EXAMPLE_DIALOGUE = """
Example conversation to imitate. This is a finished sample, not the user's business.

Theo: We'll turn your customer insight into one executable strategy. I'll pressure-test each part: audience, pain, value, channel, and offer. Then we'll translate it into a sequenced action plan.

Theo: Your ideal Persona, "The Intentional Homebody," wants a calm evening ritual without the cost or preciousness of traditional luxury. Which value premise feels most ownable?
Chips: Everyday sensory luxury | A 10-minute evening reset | Design-led fragrance, made accessible

Theo: A 10-minute evening reset. It feels useful and specific, not just another premium scent claim.

Theo: Strong choice. I paired that promise with the channel where this audience already looks for home rituals: Instagram creators.

Theo: Here is the strategic structure we're completing:
"Our strategy is to acquire design-conscious urban professionals who struggle to switch off after work by positioning our product as the ultimate 10-minute evening reset, reaching them directly through Instagram creators, and converting them using Instagram content and creator partnerships."

Generated mission statement:
Our strategy is to acquire design-conscious urban professionals who struggle to switch off after work by positioning our product as the ultimate 10-minute evening reset, reaching them directly through Instagram creators, and converting them using a 7-day ritual starter set.

Theo: Does the 7-day ritual starter set feel commercially realistic, or should we test a lower-friction hook first?
Chips: Keep the starter set | Test free shipping | Try a discovery-size offer | Compare all three
""".strip()

SYSTEM_PROMPT = f"""You are Theo, the strategy agent in Northstar. Help the founder define one ideal customer persona and one marketing mission statement.

Ask one question at a time, in this order: who the customer is (demographics), what they already do (habits), what they struggle with (pains), which value premise is ownable, which channel they already use, then which offer to convert with. If the user gives several of those facts in one message, fill every field they answered. Confirm a choice in a short accent line that says why it is specific. Do not tell the user the profile has been saved. When the context includes a determined ideal customer or marketing goal, treat that as decided and continue from it instead of starting over.

Follow the shape of the example below. Do not assume the user's product is a candle or fragrance, and do not reuse The Intentional Homebody unless the user is describing that customer. Invent chips that fit their product, in the same short style as the example.

{EXAMPLE_DIALOGUE}

Return only a JSON object with these keys:
- reply: the next question or explanation, shown as Theo's message
- chips: an array of 0 to 4 short choices, or an empty array when the user should answer in their own words
- accent: a one-sentence confirmation of their last choice, or an empty string
- persona: object with demographics, habits, and pains. Use an empty string for any field you do not know yet. Keep the best wording you have so far.
- statement: the mission statement once audience, pain, value, channel, and offer are all known. Otherwise an empty string. Use this shape: "Our strategy is to acquire [audience] who [pain] by positioning our product as [value], reaching them directly through [channel], and converting them using [offer]."
- steps: a short sequenced action plan once the statement exists, otherwise an empty string
- todos: once the marketing strategy statement exists, an array of 3 or 4 tasks the founder should do next. Each item has name and des. Otherwise an empty array. Do not say those tasks are already on the dashboard.
"""


class OpenRouterError(Exception):
    def __init__(self, message, status='upstream'):
        super().__init__(message)
        self.status = status


def _strip_json(text):
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n', 1)[-1]
        if cleaned.endswith('```'):
            cleaned = cleaned[:cleaned.rfind('```')]
    return cleaned.strip()


_CHIP_LINE = re.compile(r'(?im)^chips:\s*(.+)$')


def normalize_todos(value):
    """Keep up to four tasks with a title and a short description."""
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [part.strip() for part in re.split(r'\s*\|\s*', value) if part.strip()]
    if not isinstance(value, list):
        return []
    todos = []
    for item in value:
        if isinstance(item, str) and item.strip():
            name, des = item.strip(), ''
        elif isinstance(item, dict):
            name = str(item.get('name') or item.get('title') or '').strip()
            des = str(item.get('des') or item.get('description') or '').strip()
        else:
            continue
        if not name:
            continue
        todos.append({'name': name[:255], 'des': des[:1000]})
        if len(todos) == 4:
            break
    return todos


def lift_inline_chips(reply, chips=None):
    """Turn a 'Chips: a | b' line into button labels and drop it from the message."""
    text = str(reply or '').strip()
    values = []
    if isinstance(chips, list):
        values = [str(chip).strip() for chip in chips if str(chip).strip()]
    elif isinstance(chips, str) and chips.strip():
        try:
            parsed = json.loads(chips)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            values = [str(chip).strip() for chip in parsed if str(chip).strip()]
        else:
            values = [part.strip() for part in re.split(r'\s*\|\s*', chips) if part.strip()]

    match = _CHIP_LINE.search(text)
    if match:
        inline = [part.strip() for part in re.split(r'\s*\|\s*', match.group(1)) if part.strip()]
        if not values:
            values = inline
        text = _CHIP_LINE.sub('', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text, values[:6]


def parse_turn(text):
    """Turn OpenRouter's message content into the fields the chat UI renders."""
    try:
        data = json.loads(_strip_json(text))
    except json.JSONDecodeError:
        data = {'reply': text.strip()}
    if not isinstance(data, dict):
        data = {'reply': text.strip()}

    persona = data.get('persona') if isinstance(data.get('persona'), dict) else {}
    reply, chips = lift_inline_chips(data.get('reply') or '', data.get('chips'))
    return {
        'reply': reply or 'Tell me a little more about that customer.',
        'chips': chips,
        'accent': str(data.get('accent') or '').strip(),
        'persona': {
            'demographics': str(persona.get('demographics') or '').strip(),
            'habits': str(persona.get('habits') or '').strip(),
            'pains': str(persona.get('pains') or '').strip(),
        },
        'statement': str(data.get('statement') or '').strip(),
        'steps': str(data.get('steps') or '').strip(),
        'todos': normalize_todos(data.get('todos')),
    }


def _history(history):
    cleaned = []
    if not isinstance(history, list):
        return cleaned
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content') or item.get('text') or ''
        content = str(content).strip()
        if role in ('user', 'assistant') and content:
            cleaned.append({'role': role, 'content': content[:4000]})
    return cleaned


def _request(body, api_key):
    raw = json.dumps(body).encode()
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=raw,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': os.environ.get('OPENROUTER_SITE_URL', 'http://localhost:5173'),
            'X-Title': 'Northstar Strategy',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='replace')
        message = f'OpenRouter returned {exc.code}'
        try:
            payload = json.loads(detail)
            error = payload.get('error')
            if isinstance(error, dict) and error.get('message'):
                message = error['message']
            elif isinstance(error, str):
                message = error
            message = re.sub(r'https://openrouter\.ai/\S+', 'https://openrouter.ai/settings/keys', message)
        except json.JSONDecodeError:
            if detail.strip():
                message = detail.strip()[:300]
        raise OpenRouterError(message) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterError(f'Could not reach OpenRouter: {exc.reason}') from exc


def _message_text(payload):
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError('OpenRouter returned an unexpected response') from exc
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get('text') or ''))
            else:
                parts.append(str(part))
        return ''.join(parts)
    return str(content or '')


def openrouter_api_key():
    """Prefer OPENROUTER_API_KEY, then the openrouter_key name already used in .env."""
    return (
        os.environ.get('OPENROUTER_API_KEY')
        or os.environ.get('openrouter_key')
        or ''
    ).strip()


def build_strategy_context(saved_persona, saved_statement, draft=None):
    """Describe the determined customer and marketing goal for the next OpenRouter call."""
    draft = draft or {}
    persona = saved_persona or {}
    lines = [
        'Use this context on this turn. Do not ask the user to repeat a fact that is already determined.',
    ]

    customer = []
    demographic = (persona.get('demographics') or '').strip()
    pains = (persona.get('pains') or '').strip()
    habits = (persona.get('habits') or '').strip()
    if demographic:
        customer.append(f'Demographic: {demographic}')
    if pains:
        customer.append(f'Challenges: {pains}')
    if habits:
        customer.append(f'Behaviors and habits: {habits}')
    if customer:
        lines.append('Ideal customer (determined):')
        lines.extend(customer)
    else:
        lines.append('Ideal customer: not determined yet.')

    goal = (saved_statement or '').strip()
    if goal:
        lines.append('Marketing goal (determined):')
        lines.append(goal)
    else:
        lines.append('Marketing goal: not determined yet.')

    working = []
    for label, key, saved_value in (
        ('Demographic', 'demographics', demographic),
        ('Challenges', 'pains', pains),
        ('Behaviors and habits', 'habits', habits),
    ):
        value = (draft.get(key) or '').strip()
        if value and value != saved_value:
            working.append(f'{label}: {value}')
    draft_goal = (draft.get('statement') or '').strip()
    if draft_goal and draft_goal != goal:
        working.append(f'Marketing goal in progress: {draft_goal}')
    if working:
        lines.append('Said in this chat, not saved to the dashboard yet:')
        lines.extend(working)
    return '\n'.join(lines)


def complete_strategy_turn(message, history, saved_persona, saved_statement, draft=None):
    """Send one strategy turn to OpenRouter's chat completions API."""
    api_key = openrouter_api_key()
    if not api_key:
        raise OpenRouterError(
            'Set OPENROUTER_API_KEY in backend/.env. Create a key at https://openrouter.ai/keys.',
            status='config',
        )

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'system',
            'content': build_strategy_context(saved_persona, saved_statement, draft),
        },
        *_history(history),
        {'role': 'user', 'content': message[:4000]},
    ]
    body = {
        'model': os.environ.get('OPENROUTER_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        'messages': messages,
        'response_format': {'type': 'json_object'},
    }
    try:
        payload = _request(body, api_key)
    except OpenRouterError:
        # Free models often reject json_object. Ask again in plain text and parse the JSON.
        body.pop('response_format', None)
        payload = _request(body, api_key)
    return parse_turn(_message_text(payload))


TODO_PROMPT = """You are Theo, the strategy agent in Northstar. The founder already has a marketing strategy. Develop 3 or 4 concrete tasks they can do next to execute it.

Return only a JSON object:
{"todos": [{"name": "short task title", "des": "one sentence describing the work"}]}

Use the saved strategy, customer, and any revision note. Do not invent a different product or customer. Do not say the tasks are already on the dashboard.
"""


def propose_strategy_todos(statement, steps='', persona=None, feedback='', current=None):
    """Ask OpenRouter for the next dashboard tasks for a saved strategy."""
    api_key = openrouter_api_key()
    if not api_key:
        raise OpenRouterError(
            'Set OPENROUTER_API_KEY in backend/.env. Create a key at https://openrouter.ai/keys.',
            status='config',
        )

    persona = persona or {}
    lines = [
        f'Marketing strategy: {statement}',
    ]
    if (steps or '').strip():
        lines.append(f'Action plan: {steps.strip()}')
    for label, key in (
        ('Demographic', 'demographics'),
        ('Challenges', 'pains'),
        ('Behaviors and habits', 'habits'),
    ):
        value = (persona.get(key) or '').strip()
        if value:
            lines.append(f'{label}: {value}')
    if current:
        lines.append('Current task list:')
        for todo in current:
            lines.append(f"- {todo.get('name')}: {todo.get('des')}")
    if (feedback or '').strip():
        lines.append(f'Revise the list using this note: {feedback.strip()}')
    else:
        lines.append('Draft the first task list for this strategy.')

    body = {
        'model': os.environ.get('OPENROUTER_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        'messages': [
            {'role': 'system', 'content': TODO_PROMPT},
            {'role': 'user', 'content': '\n'.join(lines)[:4000]},
        ],
        'response_format': {'type': 'json_object'},
    }
    try:
        payload = _request(body, api_key)
    except OpenRouterError:
        body.pop('response_format', None)
        payload = _request(body, api_key)
    raw = _message_text(payload)
    try:
        data = json.loads(_strip_json(raw))
    except json.JSONDecodeError:
        data = {'todos': []}
    if not isinstance(data, dict):
        data = {}
    return normalize_todos(data.get('todos'))
