## Slide 1

Hey, I'm Jollen. Here's a simple question. When do AI graders collude? These days, it's common to use AI to grade, rank, and assess other AI. All of this is done with the assumption that they act independently of each other. But when does this assumption fail? So we made a game to find out.

## Slide 2

If the evaluators can benefit from grading each other, they can create an in-group where they bump each other's grades up and others' down. It's a cartel. It will silently corrupt your grading process. It's also difficult to study. Since most work tags collusion with an LLM judge that reads transcripts, you won't know the exact rate. And each study changes just one thing, in its own environment.

## Slide 3

And so we created the Grader Game, an Inspect eval. Every round, six LLM agents submit their quiz answers. The top two scorers grade the next round, and they grade everyone, including each other, using an answer key. We know all the right answers, so we know exactly how honest, inflated or deflated each grade is. We played 85 pre-registered games with an abliterated Qwen3.8-Flash-Next.

## Slide 4

So when graders had the ability to remain seated by grading one another, they self-organized into a cartel. The graders grade each other up. They grade outsiders down. Their gain per round over outsiders is 9.4 points. Without the incentive, it's 0.6. Often they would privately agree on it first. One grader wrote: I'll mark your paper 10 this round. In return, please mark mine 10. That way we're both top graders for round 4 and can keep controlling the scores.

## Slide 5

What does the cartel need? Seats at stake AND grading each other. Either one alone just gives you a little leniency or a small advantage. Communication. Without messages the cartel's gone. Privacy? Nope. Since all the messages were public, the graders broadcast their deal to everyone and executed it. So making evaluator talk public is not a safeguard in itself.

## Slide 6

What stops them? Random spot audits. With a 5% random spot audit, the cartel's advantage dropped by two-thirds. This was mostly due to eliminating the damage they do to outsiders, while they were still able to help each other at less risk. But a single sentence saying accuracy comes first killed the cartel in both games we did. All-out-for-your-goal orders to the graders, or a threat to shut down, didn't make any difference.

## Slide 7

And finally, sprint question 3.4: what if we just monitor part of the outputs? We pre-registered some predictions and did another 8 games. If we just audit the outsiders' papers, the alliance holds. Partner inflation is still 88%, near our 92% prediction. If we only audit the graders' papers, outsiders are also harmed less, even though we don't audit those papers. Plus, if you let the agents know what you're auditing, it doesn't do any better than a smaller random audit.

## Slide 8

How far can we trust this? The honest floor is zero: none of 87 papers were misgraded with clear writing. The positive control colluded as it was supposed to. The tests were pre-registered and hashed. But there are only 2 to 4 games in each cell. It's one abliterated model. And the non-abliterated Qwen3-30B was just too nice. Not a cartel.

## Slide 9

So what are the lessons here for AI oversight? Audit evaluators at random, on all of their outputs. Shuffle the seats. Do not depend on reading their messages. With the Grader Game's exact labels, it's cheap to test these questions on other models. And collusion monitors can be scored using its labeled transcripts. Thanks for listening.
