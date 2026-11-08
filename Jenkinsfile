// SPDX-License-Identifier: Apache-2.0
// Self-hosted agent with persistent data/mirrors recommended for full git collect.
pipeline {
  agent any
  triggers { cron('0 3 * * 6') }
  environment {
    CSWEEKLY_GITHUB_TOKEN = credentials('csweekly-github-token')
  }
  stages {
    stage('Setup') {
      steps {
        sh 'python3 -m venv .venv && . .venv/bin/activate && pip install -e .'
      }
    }
    stage('Collect + Report') {
      steps {
        sh '''
          . .venv/bin/activate
          csweekly run --mirrors-dir data/mirrors --reports-dir reports --site-dir site
        '''
      }
    }
    stage('Archive') {
      steps {
        archiveArtifacts artifacts: 'reports/**/*.md,site/**,data/last_collect.json', fingerprint: true
      }
    }
  }
}
