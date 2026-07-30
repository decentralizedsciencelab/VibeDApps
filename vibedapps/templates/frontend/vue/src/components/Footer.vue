<template>
  <footer class="bg-gray-800 text-white py-6">
    <div class="container mx-auto px-4">
      <div class="flex flex-col md:flex-row justify-between items-center">
        <div class="mb-4 md:mb-0">
          <h3 class="text-xl font-bold">DApp</h3>
          <p class="text-gray-400 mt-2">Powered by Blockchain Technology</p>
        </div>
        
        <div class="flex space-x-4">
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" class="hover:text-blue-400">
            GitHub
          </a>
          <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" class="hover:text-blue-400">
            Twitter
          </a>
          <a href="https://discord.com" target="_blank" rel="noopener noreferrer" class="hover:text-blue-400">
            Discord
          </a>
        </div>
      </div>
      
      <div class="mt-6 text-center text-gray-400">
        <p>&copy; {{ new Date().getFullYear() }} DApp. All rights reserved.</p>
      </div>
    </div>
  </footer>
</template>

<script>
export default {
  name: 'Footer'
}
</script>
