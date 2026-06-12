FROM docker.elastic.co/elasticsearch/elasticsearch:8.11.0
COPY elasticsearch-analysis-ik-8.11.0.zip /tmp/
RUN bin/elasticsearch-plugin install --batch file:///tmp/elasticsearch-analysis-ik-8.11.0.zip; \
    rm -f /tmp/elasticsearch-analysis-ik-8.11.0.zip; \
    exit 0
