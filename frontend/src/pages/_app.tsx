import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import type { AppProps } from 'next/app'
import Shell from '@/components/layout/Shell'
import '@/styles/globals.css'

const queryClient = new QueryClient()

export default function App({ Component, pageProps }: AppProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell>
        <Component {...pageProps} />
      </Shell>
      <Toaster />
    </QueryClientProvider>
  )
}