# PRINCIPLES HANDBOOK

Our goal with this document is to share some of our knowledge and expertise, in order to achieve a more efficient, happy and healthy working environment. This is a living document and we expect it to change as Monadical grows and evolves over time.

## Contents
1. [Transparency](#transparency)
2. [Feedback](#feedback)
    * [How to receive feedback](#how-to-receive-feedback)
    * [How to give feedback](#how-to-give-feedback)
3. [Trust and Verify](#trust-and-verify)
    * [Trust (and be trustworthy)](#trust-and-be-trustworthy)
    * [Verification](#verification)
4. [Be Nice](#be-nice)
5. [Professionalism](#professionalism)
6. [Check-ins and Retrospectives](#checkins-and-retrospectives)
    * [Check-ins](#check-ins)
    * [Retrospectives](#retrospectives)

## <a name="transparency">1. Transparency</a>
*We believe that free flow of information is paramount to the success of any organization. The more information a person has, the better they are able to make good decisions. Here are some ways in which we work to maximize transparency at Monadical.*

**Ask all the questions.**
There is no such thing as a stupid question, and you should never be afraid to ask if you don't understand something! Likewise, if someone asks you a question you think is silly, don't mock them, answer it genuinely and nicely.
Everyone asks silly questions from time to time, and no one likes to feel dumb.

Also, if you don't agree with something, feel free to bring it up and criticize it! Just make sure to do it respectfully--see the next section on how.

**Say what you mean, and mean what you say.**
This can take a little getting used to, but if everyone means what they say discussions become a lot easier and less like a social dance. We've found that beating around the bush causes a lot of problems, and everything goes smoother if people make an effort to be direct.

If you offer feedback to someone, assume that your critique will be received in good faith. Saying things indirectly, not at all, or sugar-coating implies that you don't trust the recipient of your critique to receive it well.

Likewise, if you say something, make sure you mean it when you say it. It's easy to blurt things out in frustration that you don't mean, and then regret it later. It's also easy to say things you half-mean, because you think that's what someone wants to hear. For example, if someone wants you to finish something and asks when it will be done, don't say you'll get around to it soon if you're not sure when you will have time.

**Checking in and out.**
Our checkins stream allows everyone in the organization to be aware of who is working on what. It also gives each of us a sense of accountability. It's very important to be honest, even if you didn't get that much done today--don't worry, everybody has bad days!

By having an accurate record of what you've done, you can look back and see if you forgot someting important from earlier in the week, or congratulate yourself if you got a lot done.

Being honest and open about our productivity helps us to find ways to improve ourselves, both individually and as a team.

**Inclusive communication.**
We try to avoid having conversations about company decisions (technical issues, operations, etc) in private mediums. Instead, they should be held in our openly-accessible zulip channels. Open-source organizations all around the world practice this because it makes it easier for everyone to see what's going on, and for concerns to be noticed addressed early before they become bigger problems. It also allows anyone with expertise in the area to review and comment.

If chats are scattered across 5 different services, it's also hard to come back and piece it all together to read the discussion fluidly.

## <a name="feedback">2. Feedback</a>

*We believe that people are happier, and more productive when they feel free to give each other feedback, and welcome it in return. Critical deliberation is a difficult skill that takes practice. Here are some of our ideas on how to approach giving and receiving.*

### <a name="how-to-receive-feedback">How to receive feedback</a>

**Every argument is a search for the best answer to some question.**
Agreeing on the question, and then figuring out the correct answer is the essence of deliberation. If you enter an argument with the intention of "winning" it, or with the goal of convincing the other person you're right, you are aiming at the wrong target.

Instead, think of it as a shared search for the best solution. The first step is to validate the critique together, and find a shared set of starting assumptions. For example:

*Max: Why is split_path calculated at the reducer? It looks like it belongs in the Animation constructor instead.*

*Nick: I put it there because if you add it to the Animation constructor then any custom Animation object needs to also implement a split_path.*

*Max: Oh, I see. Well the problem is that I'm trying to unit-test the processing, which relies on the path being split, and we probably don't want to have to set up a whole reducer just for that.*

*Nick: Testability is nice. I wonder if there's a way we can have our cake and eat it too. How about just pulling that step out into its own function and importing just that in the test?*

Nick doesn't try to convince me that his way was the "right" way. Instead, he states the concrete benefits of his design over my proposal, and within a few sentences we're brainstorming together on the same question: how to get testability into the design without damaging the ergonomics.

**All critique has value.**
Sometimes, criticism can look like a personal attack, feel harsh, or judgmental. But it's important to remember that everyone is on the same team, and that even the harshest-sounding criticism may contain a small treasure of valuable information. Each piece of feedback is an opportunity to learn; now it's your job to work together with them and make the most of it.

Even objectively incorrect feedback is an opportunity from the perspective of the team--if someone offers you a broken solution to a problem, they're shining light onto a misconception in their understanding, and are giving you the chance to help them improve.

**Fit it into the bigger picture.**
Before engaging in a discussion, it helps to think first about what outcome you're trying to achieve. What are your goals for today, this week, this month, and in your career? If someone offers you a piece of feedback, often they're just trying to help you reach one of your goals!

Take this feedback for example: "it might be better if this class were broken out into functions". Changing your code to functions may slow down your work today, but it might save you time later this week, and maybe help the design choices you make for the rest of your career. What may seem like bad feedback in the context of today, often is good feedback when you look at the big picture.

**Quick replies make the whole discussion slower.**
When someone offers feedback, stopping and thinking about it from their point of view will make your answers more convincing. Try to understand the motivation behind offering that feedback. If you frame your reply from their point of view, with their interests in mind, suddently you're not enemies, you're both on the same side working towards a common goal. Make sure to ask clarifying questions if there's any indication of a misunderstanding. If you think they're missing some context, ask them "did you know x, y, and z also affect this?" before assuming they're wrong.

### <a name="how-to-give-feedback">How to give feedback</a>

**Give feedback before you get frustrated.**
Often, putting off talking about an issue until later makes the problem worse. Small inconveniences can grow into frustration. Talking about things before people get frustrated keeps people on the same page, and no one likes to be surprised by something they never knew was a problem.

**Lead with a question.**
If you think someone has done something wrong, try asking non-accusingly about that thing. If you disagree with a decision, ask why the decision was made that way. Ask if that person considered your alternative, and if they did, try to understand why they chose their way. Often these questions lead to new discoveries on both sides, and in our experience problems discovered together in question-form make everyone more excited to find solutions.

**Offer concrete, positive recommendations.**
In our experience, everything goes smoother if the person offering feedback can describe a few concrete, actionable improvements, instead of listing general problems with the existing work. It can be hard to come up with good examples, but it's easier to identify the benefits of a concrete example, and general feedback can be easily misunderstood. Often 20 minutes spent coming up with a relevant, detailed example accomplishes more than 1 hour spent debating general ideas.

On a more theoretical note, the space of possible solutions to any problem is infinite. Therefore, telling someone a solution is bad or wrong doesn't contain much information. If there are a thousand doors and tell me not to go through door #1 I still have 999 doors to think about.

On the other hand, the space of good solutions is very small. Positive feedback is very information-dense, and likely to be much more helpful to the recipient. If there are a thousand doors and you tell me you think door #19 looks like a good option, I now have a single, concrete thing to think about. Even if I don't choose door #19, I might examine that door and learn what it is about it that drew your attention.

**Consider your objective.**
Ask yourself: What is the outcome you hope to achieve, and is that outcome what is the time/cognitive overhead/emotional investment? How can you present your feedback in a way that minimizes these costs, and maximizes the benefits?

**Be empathetic.**
Excessive criticism can be emotionally draining. People can only deal with so many problems at a time. Everyones' time is limited. Consider these things when approaching someone with feedback.

It's easy to feel attacked if criticism is directed at you personally, so instead, direct criticism at the *specific issue*. Instead of saying "You should have used recursion", try saying "Using recursion here would avoid the problem on line 154". This one is simple and easy to forget, but it's ok, with practice it becomes a habit.

Food helps everything too. It might seem silly, but feedback is much better received right after lunch than at the end of the day when everyone is tired :)


## 3. <a name="trust-and-verify">Trust and Verify</a>

*In order for a team to work well together, there must be complete trust. But blind trust isn't good either: verification processes reduce the likelihood of mistakes, which in turn increases the trust teammates can have in one another. Here is a list of principles with enable trust.*

### <a name="trust-and-be-trustworthy">Trust (and be trustworthy)</a>

**Be mindful of workflow dependencies.**
Make sure that others can rely on you, particularly in situations where their work depends on you in some way. If you say you will do something by some date, make sure you can actually do it. If you aren't able to get it done, let everyone know as soon as possible. This takes practice, but people will remember you for being reliable if you are honest when you can't make deadlines.

That being said, engineering estimates are notoriously difficult, if you're not sure about a long-term estimate, break the work into smaller tasks that are easier to estimate.

Be aware that others may make decisions based on something you say, and if something you say changes, it may change their plans. For example, something as simple as "I'll be back in 10 minutes" can cause delays in anothers' workflow if they want to ask you a question before continuing on some work, and you don't return. It's not a big deal to have a late lunch, just try to let your team know your plans.

**Assume good intentions.**
If you are frustrated by something someone does (or code someone has written), assume that that person is doing the best they can with the information they have. Often a simple 5 minute chat to see what their motivations are will resolve everything, don't be afraid to ask people questions!

If something is causing you a problem, let whomever is responsible know about your problem--maybe they aren't aware of it. Or maybe they are aware of the problem, but underestimate the consequences. People aren't aware of everyone else at all times, don't assume they caused a problem for you on purpose. Communication helps everything, just walk over and explain your situation.

You can explain the problem from your point of view, but it helps even more if you show you understand their situation and offer a solution that works for both of you.

**Assume competence.**
If you see a problem in some code, assume that whomever caused that problem did so for a reason. Find out why they did it that way--don't assume they were incompetent. Try to offer feedback only after you understand their reasoning.

**Freedom and responsibility.**
We believe that each person is different, and so everyone should have the freedom to choose their own working schedule, approach problems in their own way, etc. We believe that people who are empowered to make their own decisions are better-equipped to grow and become more effective in their work.

It is important to be responsible with that freedom. If you choose to start work at 11am, make sure you are making this decision because starting at 11am will allow you to be the most effective at work. And remember that you aren't working alone: often, problems can be better solved with real-time communication, and if your schedule doesn't overlap with other people they might not get the chance to have that experience with you.

If you have questions or concerns about your work schedule or commitments, don't hesitate to ask; we want to keep you and your family happy.

### <a name="verification">Verification</a>

**Review everything.**
All code must be reviewed before it is checked-in, two pairs of eyes catch problems better than one. Strategic decisions must also be OK'd as a team before we commit to them.

We also like to habitually review past decisions over time, everything deserves at least two perspectives: one in real-time, and one in hindsight.

Part of our strategy for achieving this is to set aside a few minutes each day to think about what we're working on and why that day (check-ins), and a few hours each month to take a look back at the work we've done and think about how it fits into the bigger picture (retrospectives).


**Question all assumptions.**
If you are depending on something someone is working on, make sure they are aware of that dependency--don't just assume they will get it done. People also work better when they know the thing they're working on will be useful to someone else!

Any time you are surprised by something, question what assumption you made that led you to being surprised. For example, if a bug breaks code you thought was working correctly, don't just fix it and move on, spend some time to figure out why it was wrong. Could better testing allow you to feel confident this kind of mistake won't happen again?

## 4. <a name="be-nice">Be nice</a>

*Sometimes it's easy to make things unpleasant for other people, without meaning to do so. A pleasant working experience is paramount to us at Monadical, and here are some ways that we try to achieve that.*

**Try to make working with you a happy experience.**
Positive feedback (I think x was good!) is not only more information-rich than negative feedback, it also makes people feel good. Remember to encourage people! People love hearing compliments, especially if it's for something you've seen them genuinely improve at.

More generally, try to avoid doing things that other people find unpleasant, and try to actively do things that make other people smile.

**Your happiness is ultimately your responsibility.**
If you are unhappy for whatever reason, remember that ultimately you are the one in control of your emotions. It is good to inform someone that something they are doing is upsetting, but it is not ok to make your feelings their responsibility. For example, don't say "I'm upset because of that thing you said," instead say "I think it would sound nicer if you said that thing differently". The difference is that *I'm upset* is not something they can control, but *sounds nicer* is.

But, regardless of other peoples' behavior, your reaction is up to you. If someone does something that is irritating, you can choose to let it affect your mood, and your work, or you can choose to address it calmly, or you can choose to ignore it. It's important to consciously separate the things that are in your control from the things that aren't, and take personal responsibility for the former.

**Acknowledgement can be cathartic**
When feeling upset, angry, or otherwise negative, it can feel cathartic to hear those feeling acknowledged by someone else. Acknowledgement is not the same as approval: for example, it is possible to acknowledge someone's feelings of frustration, even if you feel that they were wrong to let themselves reach that point.

In moments of conflict, acknowledging another's feelings first can help resolve the emotional aspects of a situation, clearing the way for a more analytical conversation about solutions or resolutions afterward.

**Escalate the medium, not the tone.**
Assume that if someone is not answering you, it is either because they are too busy to answer, or haven't seen your message. It is not because you aren't important to them.

If someone isn't answering you via email, send them a message on zulip or give them a call. If that doesn't get their attention, and what you need is especially urgent, contact someone you know is with them.

**Don't well-actually**
Often, when discussing an issue, someone will say something that is technically incorrect, but also irrelevant to the discussion. These sentences will usually start with "well, actually..." For example:

*Max: I don't like putting both 'id' and 'short_id' in this JSON on line 102.*

*Nick: Well, actually, that's not JSON, it's a dict that gets turned into JSON later.*

It's tempting to correct minor unrelated mistakes people say while talking, but it is distracting from the main point.

**Don't act surprised or outraged**
If someone doesn't know something that you know, it's an opportunity for you partake in the joy of teaching! Avoid acting shocked that they don't know it, even you are legitimately surprised. Treat the person with compassion, so that they feel happy to have learned something new, and not ashamed that they didn't know it already.

Similarly, if someone disagrees with you, assume that they either have a reason, or don't understand something that you do. In the former case, ask questions and try to understand their perspective. In the latter, help them understand yours. In both cases, acting surprised or outraged that their opinion is different will slow the process of finding agreement or a solution.

**Don't backseat-drive.**
If two people are discussing something, it can be disruptive and rude to throw in your opinion from across the room without understanding the full context. Don't half-participate in a conversation: if you want to join in a conversation others are having, be prepared to lend your full attention to it.

**No subtle -isms.**
It does not feel good to be treated differently for something that is completely outside your control, like race, gender, sexuality, or social background. And even if someone doesn't identify with a group doesn't mean it won't affect them.

However, subtle racism, sexism, homophobia, etc can happen even without intention, so we make an active effort to avoid these things.

If you notice anything that falls into an -ism category, you can point it out to the relevant person, either publicly or privately, or you can speak to one of the founders about it. Make sure to point to the problem ("comment x was homophobic") and not the person ("you are being homophobic").

**It's ok to make mistakes.**
Remember that it's easy to break any of our rules by mistake, and it shouldn't be a big deal in most cases: we just apologize and move on. Nobody is perfect! If I feel that I'm operating without making mistakes, I can usually assume that I'm either not pushing myself hard enough, or not being introspective enough.

Acknowledging our mistakes can both make those who've been affected by those mistakes feel better, and also indicate to others how we're improving. That's important because it helps our teammates gauge which learning experiences we find most valuable, and when it's important for them to step in and help in the future. Honesty with each other about our mistake-making processes help us cover for each other's faults more effectively, and sometimes we learn from one anothers' learning experience ourselves!


## 5. <a name="professionalism">Professionalism</a>

*We're a small startup now, but we have big ambitions, and to achieve great things we'll need to be the best at what we do. Here are some ways in which we strive to be great.*

**Time is precious.**
We spend a lot of time thinking about how to make the most of every moment spent working. Our lives are short, and we value free time and balance. In order to lead a healthy, balanced lifestyle, we need to use our time as effectively as possible.

We've found that things like getting exercise and sleeping well can help a lot. Also, we've found that having an explicit separation between working and free hours, and staying focused on work during work hours helps a lot. We've found that check-ins help with this.

**A big wall is made of many little bricks.**
Remember that great things are achieved one small piece at a time. If we make a small, incremental step each day towards a larger goal, sometimes we're shocked to see how far we made it a month, or a year later.

Sometimes a problem feels too big to tackle, and we end up getting frozen trying to figure out where to start. If your problem seems to big, try talking to someone about a small piece of it, and see how much of that small piece you can fit into the bigger picture. It's a lot easier to get something done if you only have to think about a little part of it at a time.

**A true master is forever a student.**
Excellence in any field involves consistent, deliberate practice. We strongly value self-improvement and learning at Monadical at every level of abstraction. We love to take the time to examine the way we talk to one another and think about how we can interact more efficiently. We're always reading about new technologies and sharing the things we discover with one another. We love to re-examine our work, even when it's good, and think about how it could be better.

## <a name="checkins-and-retrospectives">6. How to get the most out of check-ins and retrospectives</a>

Both check-ins and retrospectives are intended to be lightweight processes that improve transparency and personal accountability. Both started as experiments and have changed a bit over time.

Below is an account of how I (Max) use these processes to better myself, and I hope that others can learn from my experience. If you suspect that a tweak to one of these processes might work better for you, your contributions to the experiment are welcome!

### <a name="check-ins">Check-ins</a>

The purpose of check-ins is twofold: to communicate what I'm working on to the rest of the team, and to give myself a bit of accountability.

Every day I log what I worked on since my last check-in, and what I'm planning on doing in the immediate future.

If I'm not sure what I should be working on, I open up the *#TODO* topic and talk to the team to figure out my priorities **before** posting a check-in. This forces me to take a minute to make sure I know what I'm doing, and why.

If I don't think any of my TODOs are worth my time at the moment, I don't have any good long-term work going on, and nobody is online to discuss new work, I can always fall back on playtesting! Playtesting is never time wasted. It can also be helpful to take a look at other peoples' PRs or latest tasks in *#check-ins* and think about whether there are ways I can help them.

I don't discuss my TODOs in the *#check-ins* stream -- we have task-specific streams and topics for that. The *#check-ins* are really just for keeping a daily personal log.

Missing a day is not the end of the world--I just check in as usual the next day.

I'm careful to be honest and consistent in my check-ins stream. If I didn't get much done the day before, I don't pack it with a list of minor tasks. My teammates probably don't need to see that I answered someone's question about how to find our logging directory, for example. It's ok to have an off-day, and when I look back a month later, I want to be able to see the ebb and flow of my prodctivity.

### <a name="retrospectives">Retrospectives</a>

Retrospectives allow me to think about the work that I've done and put it into the bigger picture. It also gives me the opportunity to incorporate my manager's perspective into my own.

I'm mainly trying to answer these questions:

* What was my impact on the team since my last retrospective? Is the work I'm doing well-aligned with the goals of the team?

* Have I been using my time effectively on a day-to-day basis?

* Is there anything I'm finding difficult, or frustrated about? What is the root of the problem, and how can I overcome it?

* Are there important things that I should have or could have done, but didn't? Why?

* Are there ways that I could help my teammates be more effective, and are there ways that they could help me?

* How well am I communicating with the rest of my team? Am I efficient and assertive in communicating my thoughts? Are there things my teammates should know that they don't? Could disagreements more efficiently move toward solutions?

To this end, I thoroughly review my check-ins, and the work I've produced since the last retrospective. I go into detail--every day, the difference between what I intended to get done and what I got done offers some insight.

Over days of review, patterns usually emerge. I think about those patterns, and whether they offer solutions. Is there a way I can change my habits for the better?

All of thise is done in writing, so that I can show it to whoever is doing my retrospective with me.

Once I'm finished reviewing every day, I think about the bigger picture, and answer (again, in writing) the questions above.

I take what I've written, and send it to my manager. After they've read it over and prepared their own thoughts, we have a call to discuss it.
