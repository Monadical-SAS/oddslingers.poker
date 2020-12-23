#!/bin/bash
# This file is run after Circle CI tests to comment on github PRs
# with test output and links to screenshots of the build.

# It expects:
#     stdin <= flake8 & django test output
#
#     artifacts/           (path defined in circle.yml)
#         screenshots/
#             home.png
#             tables.png
#             leaderboard.png
#             login.png
#             about.png
# for all env vars see: https://circleci.com/docs/2.0/env-vars/

# TODO: delete all previous build comments on current PR

STDIN="$(cat)"

json_escape () {
    printf '%s' "$1" | python -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

GH_USER="monadical-sas"
GH_REPO="oddslingers.poker"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT_HASH=$(git rev-parse HEAD)
COMMIT_MSG=$(git log -1 --pretty=%B)
GH_AUTH_TOKEN=$(printenv GH_AUTH_TOKEN)
BUILD_NUM=$(printenv CIRCLE_BUILD_NUM)

CIRCLECI_TOKEN=$(printenv CIRCLECI_TOKEN)

BUILD_URL="https://circleci.com/gh/${GH_USER}/${GH_REPO}/${BUILD_NUM}#artifacts/containers/0"
ARTIFACT_URL="https://circleci.com/gh/${GH_USER}/${GH_REPO}/${BUILD_NUM}/artifacts/0/out"


COMMENT="**Build:** [#${BUILD_NUM}](${BUILD_URL})

[![](https://circleci.com/gh/monadical-sas/oddslingers.poker/tree/$BRANCH.svg?style=badge&circle-token=$CIRCLECI_TOKEN)](${BUILD_URL})

**Commit:** https://github.com/${GH_USER}/${GH_REPO}/commit/${COMMIT_HASH} **${COMMIT_MSG}**

**Desktop: [\`Home\`](${ARTIFACT_URL}/screenshots/home.png), [\`Tables\`](${ARTIFACT_URL}/screenshots/tables.png), [\`Leaderboard\`](${ARTIFACT_URL}/screenshots/leaderboard.png), [\`Login\`](${ARTIFACT_URL}/screenshots/login.png), [\`User\`](${ARTIFACT_URL}/screenshots/user.png), [\`About\`](${ARTIFACT_URL}/screenshots/about.png), [\`Support\`](${ARTIFACT_URL}/screenshots/support.png), [\`Learn\`](${ARTIFACT_URL}/screenshots/learn.png), [\`Speedtest\`](${ARTIFACT_URL}/screenshots/speedtest.png)**
**Tablet: [\`Home\`](${ARTIFACT_URL}/screenshots/home.tablet.png), [\`Tables\`](${ARTIFACT_URL}/screenshots/tables.tablet.png), [\`Leaderboard\`](${ARTIFACT_URL}/screenshots/leaderboard.tablet.png)**
**iPhone 6: [\`Home\`](${ARTIFACT_URL}/screenshots/home.iphone6.png), [\`Tables\`](${ARTIFACT_URL}/screenshots/tables.iphone6.png), [\`Leaderboard\`](${ARTIFACT_URL}/screenshots/leaderboard.iphone6.png)**
**iPhone 4: [\`Home\`](${ARTIFACT_URL}/screenshots/home.iphone4.png), [\`Tables\`](${ARTIFACT_URL}/screenshots/tables.iphone4.png), [\`Leaderboard\`](${ARTIFACT_URL}/screenshots/leaderboard.iphone4.png)**

\`\`\`
${STDIN}
\`\`\`

View More: [Build Artifacts](${BUILD_URL})"

COMMENT_JSON="{\"body\": $(json_escape "$COMMENT")}"

COMMENT_URL="https://api.github.com/repos/$GH_USER/$GH_REPO/commits/$COMMIT_HASH/comments"

#### Code to post a Github comment on the commit with build status summary

# echo "Posting comment to github commit: $COMMIT_HASH"
# echo "$COMMENT_URL"
# echo
# echo ""
# echo "-------------------------------------------------------------------"
# curl -X POST -u "$GH_USER:$GH_AUTH_TOKEN" --data "$COMMENT_JSON" "$COMMENT_URL"



curl https://monadical.zulip.sweeting.me/api/v1/messages \
    -u circleci-bot@monadical.zulip.sweeting.me:exoRY2RRXEQFQQIHwHFVmAw4g5Zt4E9t \
    -d "type=stream" \
    -d "to=bots" \
    -d "subject=oddslingers.poker" \
    -d "content=$COMMENT"


# # hand historiy dumps
# cp ./poker/tests/data/hh_*.json $HANDHISTORY_OUT || true
# cp ./poker/tests/data/*fail_*.json $HANDHISTORY_OUT || true

# # linter reports
# flake8_junit $LINT_OUT/flake8.txt $LINT_OUT/flake8.xml

# # pretty code coverage reports
# coverage combine --append ./.coverage.* || true
# # coverage html -d $COVERAGE_OUT/html

# # Create summary
# echo -e "JS Linter:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $LINT_OUT/eslint.txt >> $SUMMARY_OUT/summary.txt

# echo -e "\nJS Tests:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $TEST_OUT/javascript.txt >> $SUMMARY_OUT/summary.txt

# echo -e "\n\nJS Compilation:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $COMPJS_OUT/*.txt >> $SUMMARY_OUT/summary.txt

# echo -e "\n\nPython Linter:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $LINT_OUT/flake8.txt >> $SUMMARY_OUT/summary.txt

# echo -e "\nPython Tests:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $TEST_OUT/django.txt >> $SUMMARY_OUT/summary.txt

# echo -e "\nHandHistory Dumps:\n====================================" >> $SUMMARY_OUT/summary.txt
# ls $HANDHISTORY_OUT >> $SUMMARY_OUT/summary.txt

# echo -e "\nIntegration Tests:\n====================================" >> $SUMMARY_OUT/summary.txt
# cat $TEST_OUT/integration.txt >> $SUMMARY_OUT/summary.txt

# - run:
# name: Send reports to Github and Codecov
# when: always
# command: |
# # strip ANSI colors from output
# sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]//g" "$SUMMARY_OUT/summary.txt" > "$SUMMARY_OUT/summary_nocolor.txt"

# # post github commit comment
# ./.circleci/post_ci_hook.sh < $SUMMARY_OUT/summary_nocolor.txt

# # upload code coverage
# cd ./core
# . venv/bin/activate
# codecov -t $CODECOV_AUTH_TOKEN
