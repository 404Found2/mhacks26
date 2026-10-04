# Northstar

Northstar is an AI strategy studio. You talk with Theo, a strategy agent, until you have one customer profile, one marketing mission, and a short list of next tasks. Nothing is written to the dashboard until you approve it.

Figma Slides: https://www.figma.com/deck/zqItw5cC02DRRdnhHdiKnh
Video Demo: https://youtu.be/CB3Pix0Dj3E

## Inspiration

Founders already have plenty of advice. What they lack is a decision they can stand behind: who the customer is, what the offer is, and what to do on Monday. Generic chat leaves that as a transcript. Northstar treats the conversation as a draft and the dashboard as the record, and it only promotes a draft after the founder says so.

## What it does

Northstar has two screens.

**Marketing Strategy.** Theo asks one question at a time: who the customer is, what they already do, what they struggle with, which value is ownable, which channel they already use, and which offer should convert them. Suggested answers show up as chips you can tap, or you can type your own. When the customer profile is complete, Theo shows demographics, challenges, and habits and waits. **Keep this profile** saves it. **Revise it** keeps the interview going. The mission statement uses one shape:

> Our strategy is to acquire [audience] who [pain] by positioning our product as [value], reaching them directly through [channel], and converting them using [offer].

**Save to dashboard** stores that statement. **Not now** leaves it off the home page. After a save, Theo proposes three or four concrete tasks. **Add these tasks** puts them on the dashboard. **Revise them** asks for another pass. Chat history stays with the session, and **Reset chat** clears the thread.

**Home.** The right rail shows the saved mission statement and the target customer. Today's focus lists the approved tasks, with a progress count, a way to mark a task complete, a way to show or hide completed work, and a way to clear the list.

You can start without an account. An anonymous session holds the profile, statement, messages, and tasks. Registering or logging in attaches that session to the account.

## How we built it

The interface is React 18 and Vite. The API is Flask with SQLite. The Vite dev server proxies `/api` to Flask.

Theo's replies come from OpenRouter's chat completions API. The default model is `openrouter/free`. The server sends a system prompt that fixes the interview order and the mission-statement shape, plus a second system message with whatever is already saved. The model is asked for JSON: the next reply, chips, a short confirmation, persona fields, the statement, a short action plan, and optional tasks. The action plan is stored with the statement. The home page shows the statement itself.

The server does not trust that JSON blindly. A finished profile, statement, or task list is only inserted after an explicit chip such as **Keep this profile**, **Save to dashboard**, or **Add these tasks**. Empty model fields do not wipe values already saved. Persona, strategy, messages, and todos are keyed to the anonymous session until login, then moved onto the user.

## Challenges we ran into

Free models often reject `response_format: json_object`. The server retries once without that field and still parses JSON out of the text, including when the model wraps it in a code fence or writes chips as a `Chips:` line.

The model also wanted to save too early. We kept confirmation in the server, not the prompt, so a confident reply cannot overwrite the dashboard.

Session ownership was the other hard part. A row belongs either to an anonymous session or to a user, not both. Login has to move personas, the strategy, messages, tasks, and settings onto the account in one transaction.

## Accomplishments that we're proud of

The loop is closed. A conversation becomes a customer profile, a mission statement, and a task list, and each one waits for a yes.

The dashboard only contains what the founder kept. Refreshing the page reloads the chat and the saved strategy from SQLite.

Someone can try the product before creating an account, then keep the same work after they register.

## What we learned

A fixed statement shape made the model's output usable. Open-ended strategy prose was harder to put on a dashboard and harder to turn into tasks.

Structured output from a free model needs a fallback. The retry and the parser mattered as much as the prompt.

Confirmation gates are a product decision. The useful behavior was not "the model remembers everything." It was "the model may propose, and the founder decides what is real."

## What's next for NorthStar

- Show the saved action plan on the home page next to the mission statement.
- Let Theo set task priority. The focus list currently labels a few known sample titles and treats everything else as medium.
- Hash passwords. Accounts work for the demo; they are not production auth.
- Edit a task in place, instead of only completing it or clearing the list.
- Use the products API, which already stores a name, description, price, and margin, in the interface.

