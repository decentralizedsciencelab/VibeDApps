import '@/styles/globals.css'
import Layout from '@/components/Layout'
import { Web3Provider } from '@/contexts/Web3Context'

export default function App({ Component, pageProps }) {
  return (
    <Web3Provider>
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </Web3Provider>
  )
}
