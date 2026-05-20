MINIMAL EXAMPLE (a complete, valid WDL file with one task):

version 1.0

task hello {
  meta {
    description: "A simple hello world task"
    author: "Example Author"
    email: "author@example.org"
    url: "https://example.org"
    outputs: {
      greeting: "A text file with a greeting"
    }
  }

  parameter_meta {
    name: "Name to greet"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    String name
    Int cpu_cores = 1
    Int memory_gb = 2
  }

  command <<<
    set -eo pipefail
    echo "Hello, ~{name}!" > greeting.txt
  >>>

  output {
    File greeting = "greeting.txt"
  }

  runtime {
    docker: "ubuntu:22.04"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}
