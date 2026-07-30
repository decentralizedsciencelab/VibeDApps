import Head from 'next/head'

export default function About() {
  return (
    <>
      <Head>
        <title>DApp - About</title>
        <meta name="description" content="About our DApp" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8 text-center">About Our DApp</h1>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <p className="mb-4">
            This is a decentralized application (DApp) built with Next.js and Ethereum blockchain technology.
          </p>
          <p className="mb-4">
            It allows users to interact with smart contracts on the Ethereum blockchain in a user-friendly way.
          </p>
          <p>
            Features include:
          </p>
          <ul className="list-disc ml-6 mt-2">
            <li>Connect with MetaMask or other Web3 wallets</li>
            <li>Interact with smart contracts</li>
            <li>View transaction history</li>
            <li>Real-time updates</li>
          </ul>
        </div>
      </div>
    </>
  )
}
