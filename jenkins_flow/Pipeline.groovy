import groovy.json.JsonSlurper

def notify(msg, color = "green", also_echo = true) {
    json_friendly = msg.replace("\n","\\n")
    sh """curl -d '{"color":"${color}","message":"${json_friendly}","notify":false,"message_format":"text"}' -H 'Content-Type: application/json' ${NOTIFICATION_ENDPOINT}"""
    if(also_echo){
        echo msg
    }
}

def fail(msg, color = "red") {
    notify(msg, color, false)
    error(msg)
}


def _checkout( repo_url, branch, directory_name){
    checkout([
        $class: 'GitSCM',
        branches: [[name: "${branch}"]],
        doGenerateSubmoduleConfigurations: false,
        extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${directory_name}"]],
        submoduleCfg: [],
        userRemoteConfigs: [[url: "${repo_url}"]]
    ])
}

def TUBULAR_REPO_URL = "https://github.com/edx/tubular.git"

node {
    notify("Starting dummy-deploy pipeline to deploy PR #${PR_NUMBER} to dummy-environment")
}

node {
    env.REPO_ID = 49974806
    notify("Checking to see if the PR(#${PR_NUMBER}) is against the live branch(${LIVE_BRANCH}).")
    sh "virtualenv venv"
    _checkout("${TUBULAR_REPO_URL}", "${TUBULAR_BRANCH}", "tubular")

    try {
        sh ". venv/bin/activate; pip install -r tubular/scripts/github/requirements.pip; python tubular/scripts/github/check_pr_against_branch.py -r ${env.REPO_ID} -p ${PR_NUMBER} -b ${LIVE_BRANCH}"
    } catch (e) {
        fail("PR is not against ${LIVE_BRANCH}")
    }

    echo("PR is against ${LIVE_BRANCH}, so grabbing the hash.")
    def api = new URL("https://api.github.com/repos/edx/dummy-webapp/pulls/${PR_NUMBER}").text
    def pr = new JsonSlurper().parseText(api)
    env.PR_SHA = pr.head.sha
}

parallel([
    "foo": {
        node {
            notify("Check to make sure commit has passed tests.")
            sh "virtualenv venv"
        _checkout("${TUBULAR_REPO_URL}", "${TUBULAR_BRANCH}", "tubular")
        try {
                sh ". venv/bin/activate; pip install -r tubular/scripts/github/requirements.pip; python tubular/scripts/github/check_pr_tests_status.py -c ${env.PR_SHA} -r ${env.REPO_ID}"
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
    },
   "failFast": true])

node {
    echo "Build step."
    notify("Building artifact. Eventually AMI, just an archive for now.")
    sh "ls -al"
    _checkout("https://github.com/${DUMMY_WEBAPP_ORG}/${DUMMY_WEBAPP_NAME}.git", "${env.PR_SHA}", "${DUMMY_WEBAPP_NAME}")
    sh "ls -al"
}

node {
    notify("Waiting for user input before we deploy (#${PR_NUMBER}:${env.PR_SHA}) to dummy environment.\n${env.BUILD_URL}/console")
    sleep 5
    input "Ready to deploy?"
}

node {
    sleep 10
    notify("Deployed the dummy app!")
}
