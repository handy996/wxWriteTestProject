FROM maven:3.9.11-eclipse-temurin-21@sha256:6fdc855a6ed81d288ca7ca37ac6ff5e9308b612485c0801d70b25a858c83d237 AS build
WORKDIR /build/backend
COPY backend/pom.xml .
COPY backend/src src
# ArticleAstTest reads the frozen contract vectors from the repository layout.
COPY docs/schemas/editorial.schema.json /build/docs/schemas/editorial.schema.json
COPY tests/fixtures/contracts/T00/rc3 /build/tests/fixtures/contracts/T00/rc3
RUN mvn -B -ntp verify

FROM eclipse-temurin:21-jre-jammy@sha256:f04fb34e053148344e83317976114ec3f37e4b830ec8bdab5a2fe3cecd7d010b
WORKDIR /app
RUN groupadd --gid 10001 editorial && useradd --uid 10001 --gid editorial --no-create-home editorial
COPY --from=build /build/backend/target/editorial-0.1.0-SNAPSHOT.jar /app/editorial.jar
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/editorial.jar"]
