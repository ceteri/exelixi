data <- read.delim('~/src/exelixi/doc/tsp_fitness.tsv', header=F)
plot(ecdf(data$V1), main="TSP fitness distribution", xlab="fitness value", ylab="CDF")
abline(h=.8, col="blue")