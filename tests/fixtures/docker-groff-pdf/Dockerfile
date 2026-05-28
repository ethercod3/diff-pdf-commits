FROM alpine:3.22

RUN apk add --no-cache groff

COPY build-pdf /usr/local/bin/build-pdf
RUN chmod +x /usr/local/bin/build-pdf

WORKDIR /work
ENTRYPOINT ["build-pdf"]
