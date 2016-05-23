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

