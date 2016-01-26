import groovy.json.JsonSlurper

def notify(msg, color = "green", also_echo = true) {
    /*sh """curl -d '{"color":"${color}","message":"${msg}","notify":false,"message_format":"text"}' -H 'Content-Type: application/json' ${NOTIFICATION_ENDPOINT}"""*/
    if(also_echo){
        echo msg
    }
}

def fail(msg, color = "red") {
    notify(msg, color, false)
    error(msg)
}

node {
    notify("Starting dummy-deploy pipeline to deploy PR #${PR_NUMBER} to dummy-environment")
}

node {
    env.REPO_ID = 49974806
    notify("Checking to see if the PR(#${PR_NUMBER}) is against the live branch(${LIVE_BRANCH}).")
    sh "virtualenv venv"
    git url: "https://github.com/edx/tubular.git", branch: "${TUBULAR_BRANCH}"

    try {
        sh ". venv/bin/activate; pip install -r scripts/github/requirements.pip; python scripts/github/check_pr_against_branch.py -r ${env.REPO_ID} -p ${PR_NUMBER} -b ${LIVE_BRANCH}"
    } catch (e) {
        fail("PR is not against ${LIVE_BRANCH}")
    }

    echo("PR is against ${LIVE_BRANCH}, so grabbing the hash.")
    def api = new URL("https://api.github.com/repos/edx/dummy-webapp/pulls/${PR_NUMBER}")
    def pr = new JsonSlurper().parseText(api.text)
    env.PR_SHA = pr.head.sha
}

parallel([
    "foo": {
        node {
            notify("Check to make sure commit has passed tests.")
            sh "virtualenv venv"
            git url: "https://github.com/edx/tubular.git", branch: "${TUBULAR_BRANCH}"
	    try {
                sh ". venv/bin/activate; pip install -r scripts/github/requirements.pip; python scripts/github/check_pr_tests_status.py -c ${env.PR_SHA} -r ${env.REPO_ID}"
	    } catch (e) {
                fail("PR failed some tests.  Please check https://github.com/${DUMMY_WEBAPP_ORG}/${DUMMY_WEBAPP_NAME}/pull/${PR_NUMBER}")
            }
            notify("Commit(${env.PR_SHA}) has passed all tests.")
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
    notify("Building artifact. Eventually AMI, just an archive for now.")
    sh "git clone https://github.com/${DUMMY_WEBAPP_ORG}/${DUMMY_WEBAPP_NAME}.git; cd ${DUMMY_WEBAPP_NAME}; git checkout ${env.PR_SHA}"
    sh "ls -al"
}

node {
    sleep 5
    notify("Waiting for user input before we deploy (#${PR_NUMBER}:${env.PR_SHA}) to dummy environment.\n${env.BUILD_URL}/console")
    input "Ready to deploy?"
}

node {
    sleep 10
    notify("Deployed the dummy app!")
}
