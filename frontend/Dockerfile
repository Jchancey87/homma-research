# Stage 1: Build the application
FROM node:18-alpine AS builder

WORKDIR /app

# Install pnpm compatible with Node 18
RUN npm install -g pnpm@9

# Copy package files and install dependencies
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# Copy the rest of the frontend code
COPY . .

# Add build-time env vars for Next.js
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build the Next.js application
RUN pnpm run build

# Stage 2: Run the application
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV production

# Install pnpm for runtime script execution
RUN npm install -g pnpm@9

# Copy built artifacts from builder stage
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Expose the port Next.js runs on
EXPOSE 3000

# Start the application
CMD ["pnpm", "start"]
