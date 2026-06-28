# JRE 运行 — 需先本地执行 mvn package -DskipTests
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY allahpan-search/target/*.jar app.jar
EXPOSE 8081
ENV SPRING_PROFILES_ACTIVE=dev,docker
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
