node {
    echo "Poll SCM"
    sh "virtualenv venv"
    git url: "https://github.com/edx/tubular.git", branch: "${TUBULAR_BRANCH}"
    sh ". venv/bin/activate; pip install -r scripts/github/requirements.pip; python scripts/github/check_pr_against_branch.py -r 49974806 -p ${PR_NUMBER} -b ${LIVE_BRANCH}"
}

parallel([ "foo":
{node {
    echo "Node 1"
    sleep 30
}},
"bar":
{node {
    echo "Node 2"
    sleep 30
}}])

node {
    echo "Build step."
    echo "Collect some artifacts"
    sleep 5
}

node {
    sleep 5
    input "Ready to deploy?"
}

node {
    sleep 10
    echo "Deploy the dummy app!"
}
