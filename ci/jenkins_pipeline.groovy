/**
 * AutoFix-Skill Jenkins Pipeline
 *
 * This pipeline can be used to integrate autofix-skill
 * into Jenkins-based CI/CD workflows.
 */

pipeline {
    agent {
        docker {
            image 'python:3.10-slim'
            args '-u root'
        }
    }

    environment {
        PYTHONPATH = '.'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {
        stage('Setup') {
            steps {
                dir('autofix_skill') {
                    sh 'pip install --upgrade pip'
                    sh 'pip install pytest pytest-cov'
                }
            }
        }

        stage('Unit Tests') {
            steps {
                dir('autofix_skill') {
                    sh '''
                        PYTHONPATH=. python -m pytest \
                            tests/test_basic.py \
                            tests/test_symbol_dep.py \
                            tests/test_parser.py \
                            -v --junitxml=test-results.xml
                    '''
                }
            }
            post {
                always {
                    junit 'autofix_skill/test-results.xml'
                }
            }
        }

        stage('Integration Tests') {
            steps {
                dir('autofix_skill') {
                    sh '''
                        PYTHONPATH=. python -m pytest \
                            tests/integration/ \
                            -v --junitxml=integration-results.xml
                    '''
                }
            }
            post {
                always {
                    junit 'autofix_skill/integration-results.xml'
                }
            }
        }

        stage('AutoFix on Failure') {
            when {
                expression {
                    return env.BUILD_LOG_FILE != null
                }
            }
            steps {
                dir('autofix_skill') {
                    script {
                        def result = sh(
                            script: """
                                PYTHONPATH=. python -m src.cli fix \
                                    --log "${env.BUILD_LOG_FILE}" \
                                    --ci --json
                            """,
                            returnStatus: true
                        )

                        if (result == 0) {
                            echo 'AutoFix completed successfully'
                        } else {
                            echo 'AutoFix encountered issues'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check logs for details.'
        }
    }
}
