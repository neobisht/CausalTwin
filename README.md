# CausalTwin


Author: Shiv Bisht | Date: 14 September 2026


Problem
Our systems today show Copilot upsell in isolation, meaning we show multiple upsell to users across WXP, MCA both persisent and contextual. Over time we will increase the contextual upsell even more.
That works for the current moment, but it misses what happens after. Showing one offer can change how the user reacts to the next one.
For example, an image-generation upsell may make a later Copilot offer more relevant. But two offers shown too close together may just annoy the user. In some cases, skipping an offer now may lead to a better conversion opportunity later.

Why current system Struggle

1. They optimize for the current moment: Most of our systems optimize for the immediate conversion. They do not really understand how different offers interact over time.
2. Frequency Caps are Static: This treats all offers, users and situations equally. But users have different tolerance levels, and different offers interact differently. Three related upsells may create significantly more fatigue than three unrelated ones.
3. Cross Offer effects are invisible: Existing analytics can tell us: CTR conversion rate purchases dismissals abandonment But they rarely tell us: “Showing Offer A reduced conversion on Offer B six hours later.” These interactions can remain hidden because the two events may belong to different features, teams or surfaces. This creates a blind spot in monetization systems.
4. We cannot test every possible journey: A/B experiments are designed around a single feature, message or surface. In reality, users move through sequences of monetization experiences. The effect of one experiment may therefore depend on what the user saw before it and what they see afterward.
Testing every possible sequence on real users is impractical.
Even a small system with 10 potential intervention points and three possible actions, show, defer or suppress,  creates: 59,049 possible journeys.
Real-world experimentation cannot efficiently explore this space.

What we are Missing
Today, we can measure things like: clicks, conversions, dismissals, purchases. But it is much harder to answer questions like: “Did showing "Upsell/Offer A" reduce the chance that "Upsell B" would convert later?” Or: “Would we have made more money if we had skipped the first offer?” These effects are hard to see because they happen across different times, features and product surfaces.

Why this matters / Business Risk
If we optimize every offer independently, we may end up showing too many upsell in product. That can:

- annoy users,
- reduce trust,
- reduce future conversion,
- waste good monetization opportunities,
- increase the number of prompts needed to get a purchase.
The system may improve short-term conversion while hurting long-term value.

Opportunity
There is an opportunity to move growth optimization from: 
independent offer targeting to: long-term intervention sequencing.
Instead of treating every upsell as an isolated conversion opportunity, the system could understand how interventions interact over time and optimize the sequence of offers around the user. 
The goal would no longer be to maximize conversion on every impression. It would be to maximize long-term value while minimizing unnecessary commercial interruptions. 
The core unanswered question becomes: What is the right sequence of interventions for this user, and which opportunities should we intentionally not use?

Hypothesis 
If we use synthetic users to simulate different upsell journeys and learn how one offer affects the next, we can make better decisions on when to show, delay, or skip an offer.
This should help us reduce unnecessary upsell prompts while improving long-term conversion.
Note: Synthetic users are AI-generated profiles and behavioral models that simulate the thoughts, needs, and actions of real target audiences

Success Metrics
Primary

- Long-term conversion rate across the full user journey
Secondary

- Offers shown per user
- Conversion per offer shown
- User fatigue / dismissals
- Incremental revenue per user
- Accuracy of synthetic predictions vs. real experiment results

Prototype success
This prototype is successful if it can:

- simulate multiple offer sequences for the same user
- identify when one offer helps or hurts a future offer
- recommend show, delay, or skip
- outperform a simple frequency-cap or always-show baseline in simulation
