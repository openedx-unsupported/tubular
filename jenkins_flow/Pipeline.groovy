import groovy.json.JsonSlurper

node {
    env.REPO_ID = 49974806
    echo "Check to see if the PR is against the correct branch."
    sh "virtualenv venv"
    git url: "https://github.com/edx/tubular.git", branch: "${TUBULAR_BRANCH}"
    sh ". venv/bin/activate; pip install -r scripts/github/requirements.pip; python scripts/github/check_pr_against_branch.py -r ${env.REPO_ID} -p ${PR_NUMBER} -b ${LIVE_BRANCH}"

    echo "PR is passing so grabbing the hash."
    def api = new URL("https://api.github.com/repos/edx/dummy-webapp/pulls/${PR_NUMBER}")
    def pr = new JsonSlurper().parseText(api.text)
    env.PR_SHA = pr.head.sha

}


parallel([
    "foo": {
        node {
            echo "Check to make sure commit has passed tests."
            sh "virtualenv venv"
            git url: "https://github.com/edx/tubular.git", branch: "${TUBULAR_BRANCH}"
            sh ". venv/bin/activate; pip install -r scripts/github/requirements.pip; python scripts/github/check_pr_tests_status.py -c ${env.PR_SHA} -r ${env.REPO_ID}"
        }
    },
    "bar": {
        node {
            echo "Node 2"
            sleep 30
        }
    }
])

node {
    echo "Build step."
    echo "Collect some artifacts"
    /*    git url: "${DUMMY_WEBAPP_URL}", branch: env.PR_SHA */
    sh "git clone ${DUMMY_WEBAPP_URL} dummy_webapp; cd dummy_webapp; git checkout ${env.PR_SHA}"
    sh "ls -al"
}

node {
    sleep 5
    input "Ready to deploy?"
}

node {
    sleep 10
    echo "Deploy the dummy app!"
}
