# tubular

## Overview
Python scripts for integrating pipelines with various services/tools such as:
* Asgard
* Amazon Web Services EC2
* GitHub
* Jenkins
* Drupal

The scripts perform work to enable continuous delivery (CD) for https://edx.org. These scripts are called from various tasks/jobs/stages in GoCD pipelines - but could be called from any automation/CD framework.

## Configuration
```
pip install .
```

## Testing
```
tox
```

## License

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

## How To Contribute

Contributions are very welcome.

Please read [How To Contribute](https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst) for details.

Even though they were written with ```edx-platform``` in mind, the guidelines
should be followed for Open edX code in general.

## Reporting Security Issues

Please do not report security issues in public. Please email security@edx.org.

## Environment variables

|     Variable Name    | Default                         | Description                                                                                   |
|:--------------------:|---------------------------------|-----------------------------------------------------------------------------------------------|
| ASGARD_API_ENDPOINTS | http://dummy.url:8091/us-east-1 | fully qualified URL to the asgard instance to run the scripts against                         |
| ASGARD_API_TOKEN     | dummy-token                     | String - The asgard token                                                                     |
| ASGARD_WAIT_TIMEOUT  | 600                             | Integer - time in seconds to wait for an action such as instances healthy in a load balancer. |
| REQUESTS_TIMEOUT     | 10                              | How long to wait for an http connection/response from Asgard.                                 |
| RETRY_MAX_ATTEMPTS   | 5                               | Maximum number attempts to be made when asgard returns a 400 or 500 response.            |
| RETRY_DELAY_SECONDS  | 5                               | How long in seconds to wait between retries to asgard                                         |
| RETRY_MAX_TIME_SECONDS | None                          | How long in seconds to keep retrying asgard before giving up.                                 |
| RETRY_FACTOR         | 1.5                             | Factor to multiple the base wait time by per retry attempt.  Only applies to ec2 boto calls   |
| ASGARD_ELB_HEALTH_TIMEOUT | 600                        | How long in seconds to wait for an instanced to become healthy in an ELB.                     |
| SHA_LENGTH           | 10                              | Length of the commit SHA to use when querying for a PR by commit.                             |
| BATCH_SIZE           | 18                              | Number of commits to batch together when querying a PR by commit.                             |