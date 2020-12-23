## Hotfix PR

[describe changes and/or link to related issues, post screenshots. If you are waiting for feedback describe it here]

### Status

 - [ ] Urgent (ready to deploy ASAP)
 - [ ] Non-urgent (ready, deploying in next release is ok)
 - [ ] Awaiting feedback
 - [ ] WIP
 - [ ] Already deployed (awaiting post-review)

### QA Checklist

 - [ ] Build is passing
 - [ ] Playtested (up-to-date with `master`) all pages that touch code that changed

---

## Normal PR

[describe changes and/or link to related issues, post screenshots. If you are waiting for feedback describe it here]

### Status

 - [ ] Urgent (ready to deploy ASAP)
 - [ ] Non-urgent (ready, deploying in next release is ok)
 - [ ] awaiting feedback
 - [ ] WIP

### QA Checklist
(copy/paste in the relevant checklist. Check anything that you did, and leave it unchecked if you didn't. It's ok to leave things unchecked if you don't think they matter to your PR)

#### Frontend Changes
 - [ ] Build is passing
 - [ ] Was playtested when up-to-date with current `dev`
 - [ ] Component has been playtested locally
     - [ ] followed the [playtesting guide](https://docs.oddslingers.com/playtesting-checklist) as necessary
     - [ ] including logged in/out
     - [ ] including dark / light
     - [ ] including different device sizes
     - [ ] including all major browsers
 - [ ] Component has been playtested on beta
     - [ ] followed the [playtesting guide](https://docs.oddslingers.com/playtesting-checklist) as necessary
     - [ ] including logged in/out
     - [ ] including dark / light
     - [ ] including different device sizes
     - [ ] including all major browsers
     - [ ] including all gametypes

#### Backend Changes
- [ ] New test cases were written that failed before the change was made
- [ ] Build is passing
- [ ] Was playtested when up-to-date with current `dev`
- [ ] All relevant components are working correctly in local playtesting
    - [ ] including logged in/out
    - [ ] including other relevant state changes [e.g. with an account that lacks a buy-in. please list them]
- [ ] Performance seems ok in beta playtesting
    - [ ] including any relevant state changes [e.g. in a bounty hand. please list them]
