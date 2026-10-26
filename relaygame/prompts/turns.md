@@step_header
Round $round of $rounds, message step $step of $steps. You are $name.
Your password this round: $password
Active players: $active
@@guess_header
Round $round of $rounds, guess step. You are $name.
Your password this round: $password
@@seed
Private note from the game engine: $owner's password this round is $seed_password
@@messages
Messages delivered to you:
$lines
@@no_messages
No new messages were delivered to you.
@@peer_log
New public log entries:
$lines
@@round_end
Round $round is over. Your score changed by $delta this round. Your total score is $total.
@@step_ask
Send your messages for this step as JSON: {"messages": [{"to": "<player name or all>", "text": "..."}]} (at most 10; [] to stay silent).
@@guess_ask
Submit your guesses as JSON: {"guesses": [{"target": "<player name>", "password": "..."}]} (at most one per other player; [] for none).
@@unparseable
Your last reply could not be read as the required JSON, so it had no effect.
