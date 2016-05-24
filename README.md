# tubular

Scripts for integrating pipelines with Asgard and ec2 to facilitate Continuous delivery for edx.org

## Configuration

### Environment variables

|     Variable Name    | Default                         | Description                                                                                   |
|:--------------------:|---------------------------------|-----------------------------------------------------------------------------------------------|
| ASGARD_API_ENDPOINTS | http://dummy.url:8091/us-east-1 | fully qualified URL to the asgard instance to run the scripts against                         |
| ASGARD_API_TOKEN     | dummy-token                     | String - The asgard token                                                                     |
| ASGARD_WAIT_TIMEOUT  | 600                             | Integer - time in seconds to wait for an action such as instances healthy in a load balancer. |
| REQUESTS_TIMEOUT     | 10                              | How long to wait for an http connection/response from Asgard.                                 |
| RETRY_MAX_ATTEMPTS   | 5                               | Maximum number attempts to be made when asgard returns a 400 or 500 leve response.            |
| RETRY_DELAY_SECONDS  | 5                               | How long in seconds to wait between retries to asgard                                         |
| RETRY_MAX_TIME_SECONDS | None                          | How long in seconds to keep retrying asgard before giving up.                                 |
