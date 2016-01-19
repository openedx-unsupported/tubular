# To build the docker image: docker build -t local/jenkins .
# To run using this image: docker run -t -i -p 8080:8080 -p 50000:50000 -v /path/to/jenkins_folder:/var/jenkins_home local/jenkins
FROM jenkins
USER root
RUN apt-get update && apt-get install -y virtualenv
USER jenkins
