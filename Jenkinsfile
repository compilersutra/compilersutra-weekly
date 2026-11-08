// SPDX-License-Identifier: Apache-2.0
// Optional: self-hosted agent with persistent data/mirrors for llvm-project + gcc.
pipeline {
  agent any
  triggers { cron('0 3 * * 6') } // Saturday 03:00
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
          csweekly run --mirrors-dir data/mirrors --reports-dir reports
        '''
      }
    }
    stage('Archive') {
      steps {
        archiveArtifacts artifacts: 'reports/**/*.md,data/last_collect.json', fingerprint: true
      }
    }
  }
}
