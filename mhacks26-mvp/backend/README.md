# Northstar Backend

Flask-based REST API for the Northstar AI Strategy Studio application.

## Setup

### Prerequisites
- Python 3.8+
- pip

### Installation

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python -c "from app import init_db; init_db()"
```

5. Run the server:
```bash
python app.py
```

The API will be available at `http://localhost:5000`

## OpenRouter strategy chatbot

The Marketing Strategy screen keeps the existing example conversation on screen, then interviews the user for their own ideal customer and marketing mission statement. Each reply comes from [OpenRouter's chat completions API](https://openrouter.ai/docs/api-reference/chat-completion): `POST https://openrouter.ai/api/v1/chat/completions`.

### 1. Create a key

Create a key at [https://openrouter.ai/keys](https://openrouter.ai/keys). OpenRouter bills the model you choose, so the key needs credit for that model.

### 2. Configure the backend

```bash
cp .env.example .env
```

Set `OPENROUTER_API_KEY` in `backend/.env`. A key saved as `openrouter_key` is also accepted. The server reads that file on startup and does not override variables already exported in the shell. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Bearer token sent as `Authorization: Bearer …` |
| `OPENROUTER_MODEL` | Model id from the [OpenRouter model list](https://openrouter.ai/models). Default: `openrouter/free`, the [free-model router](https://openrouter.ai/openrouter/free) |
| `OPENROUTER_SITE_URL` | Sent as OpenRouter's `HTTP-Referer` attribution header. Default: `http://localhost:5173` |

The app also sends `X-Title: Northstar Strategy`. The default model is `openrouter/free`, which picks an available free model for each request so the call is not billed. Set `OPENROUTER_MODEL` to a specific model id if you want a different one.

### 3. What the server sends

`POST /api/chat` accepts the session cookie and:

```json
{
  "message": "College students in Ann Arbor who have no free time",
  "history": [
    {"role": "assistant", "content": "Who is the customer you most want this strategy to reach?"},
    {"role": "user", "content": "Students who scroll instead of winding down"}
  ]
}
```

The server adds the system prompt. That prompt includes the Marketing Strategy example (the Intentional Homebody, the value chips, the mission-statement template, and the offer chips) and asks the model for a JSON object. The OpenRouter body looks like this:

```json
{
  "model": "openrouter/free",
  "messages": [
    {"role": "system", "content": "You are Theo..."},
    {"role": "system", "content": "Already saved for this session: {...}"},
    {"role": "user", "content": "College students in Ann Arbor who have no free time"}
  ],
  "response_format": {"type": "json_object"}
}
```

If the selected model rejects `response_format`, the server retries once without it and still parses JSON from the reply.

### 4. What gets saved

The model returns `reply`, `chips`, `accent`, `persona` (`demographics`, `habits`, `pains`), `statement`, and `steps`.

- Persona fields are upserted into the `personas` table for the current anonymous session, or for the user after login.
- A completed mission statement is upserted into `strategy.statement`, with `steps` on the same row.
- Empty fields do not wipe values already saved.

`POST /api/chat` responds with:

```json
{
  "message": "What do they already do when this problem shows up?",
  "chips": ["Scroll between classes", "Study late", "Buy a quick treat"],
  "accent": "",
  "statement": "",
  "persona": {"id": 1, "demographics": "College students in Ann Arbor", "habits": "", "pains": ""},
  "strategy": null
}
```

The chat renders `message` as Theo's bubble, `chips` as choices, `accent` as the highlighted confirmation, and `statement` in the generated strategy box. Without `OPENROUTER_API_KEY`, the route returns `503` and the chat shows how to set the key.

## Features

- **Anonymous Sessions**: Users can start using the app immediately without login
- **Session Management**: Automatic session creation and management via SQLite3
- **User Authentication**: Optional login/registration for registered users
- **Data Persistence**: All personas, strategies, products, and todos are saved per session/user
- **RESTful API**: Clean, intuitive endpoints for all operations

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user

### Session
- `GET /api/session` - Get current session info

### Personas
- `GET /api/personas` - Get all personas
- `POST /api/personas` - Create new persona
- `PUT /api/personas/<id>` - Update persona

### Strategy chat
- `POST /api/chat` - Next OpenRouter turn. Saves persona and mission statement for the session.

### Strategy
- `GET /api/strategy` - Get all strategies
- `POST /api/strategy` - Create new strategy
- `PUT /api/strategy/<id>` - Update strategy

### Products
- `GET /api/products` - Get all products
- `POST /api/products` - Create new product
- `PUT /api/products/<id>` - Update product
- `DELETE /api/products/<id>` - Delete product

### Todos
- `GET /api/todos` - Get all todos
- `POST /api/todos` - Create new todo
- `PUT /api/todos/<id>` - Update todo
- `DELETE /api/todos/<id>` - Delete todo

### Health
- `GET /api/health` - Health check

## Session Flow

1. User visits the app
2. Backend automatically creates an anonymous session
3. Session ID is stored in Flask session (browser cookie)
4. All data operations use session ID until user logs in
5. Upon login, data can be linked to user account

## Database

The app uses SQLite3 with the schema defined in `schemas.sql`. The database file is created automatically on first run.

## Environment Variables

- `OPENROUTER_API_KEY` - Required for `POST /api/chat`. See the OpenRouter section above.
- `OPENROUTER_MODEL` - OpenRouter model id (default: `openrouter/free`)
- `OPENROUTER_SITE_URL` - `HTTP-Referer` header sent to OpenRouter
- `SECRET_KEY` - Flask session secret (default: 'dev-secret-key-change-in-production')
- `DATABASE_PATH` - Path to SQLite database file (default: `northstar.db` in this directory)
