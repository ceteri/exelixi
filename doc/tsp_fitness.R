data <- read.delim('/Users/ceteri/Desktop/fitness.tsv', header=F)
plot(ecdf(data$V1), main="TSP fitness distribution", xlab="fitness value", ylab="CDF")