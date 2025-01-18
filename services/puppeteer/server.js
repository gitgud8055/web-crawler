// Import required modules
const express = require("express");
const puppeteer = require("puppeteer");
const { Readable } = require("stream");
const cheerio = require("cheerio");

// Create an Express app
const app = express();
const PORT = 2000;

// Middleware to parse JSON requests
app.use(express.json());

async function fetchDynamicHTML(url, stream, headless = "new") {
  try {
    // Launch a new browser instance
    const browser = await puppeteer.launch({
      headless: headless, // Allows switching between headless and non-headless mode
      args: ["--start-maximized"],
    });

    // Open a new page
    const page = await browser.newPage();

    // Set a user agent to mimic a regular browser
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Safari/537.36"
    );
    await page.setJavaScriptEnabled(true);
    // Navigate to the target URL
    await page.goto(url, { waitUntil: "networkidle2" });

    // Optionally wait for specific elements to load if needed
    await page.waitForSelector("body");

    // Get the rendered HTML content
    const html = await page.evaluate(() => {
      return document.documentElement.outerHTML;
    });
    const timestamp = Date.now();

    // Close the browser
    await browser.close();

    // Push JSON to stream immediately
    stream.push(JSON.stringify({ url, timestamp, html }) + "\n");

    return html;
  } catch (error) {
    console.error("Error fetching rendered HTML:", error);
    throw error;
  }
}

// Function to extract URLs from HTML
function extractUrls(html, baseUrl) {
  const $ = cheerio.load(html);
  const urls = [];

  $("a[href]").each((_, element) => {
    let href = $(element).attr("href");
    if (href.startsWith("/")) {
      href = new URL(href, baseUrl).toString();
    }
    if (href.startsWith("http")) {
      urls.push(href);
    }
  });

  return urls;
}

// Recursive function to fetch all URLs up to a max depth, ensuring same domain
async function fetchUrlsRecursively(
  url,
  maxDepth,
  currentDepth,
  stream,
  baseDomain
) {
  if (currentDepth > maxDepth) return;

  try {
    const html = await fetchDynamicHTML(url, stream);
    const childUrls = extractUrls(html, url);

    for (const childUrl of childUrls) {
      const childDomain = new URL(childUrl).hostname;
      if (childDomain === baseDomain) {
        await fetchUrlsRecursively(
          childUrl,
          maxDepth,
          currentDepth + 1,
          stream,
          baseDomain
        );
      }
    }
  } catch (error) {
    console.error(
      `Error processing URL ${url} at depth ${currentDepth}:`,
      error
    );
  }
}

// POST route to fetch HTML and follow links
app.post("/fetch-html", async (req, res) => {
  const { url, depth } = req.body;

  if (typeof depth !== "number" || depth < 1) {
    return res
      .status(400)
      .json({ url: url, error: "A valid maxDepth is required" });
  }

  // Set headers to enable streaming response
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Transfer-Encoding", "chunked");
  const stream = new Readable({
    read() {},
  });

  stream.pipe(res);

  try {
    const baseDomain = new URL(url).hostname;
    await fetchUrlsRecursively(url, depth, 1, stream, baseDomain);
  } catch (error) {
    console.error("Error processing URL", url, ":", error);
    const timestamp = Date.now();
    stream.push(
      JSON.stringify({ url, timestamp, error: "Failed to process URL" }) + "\n"
    );
  }

  stream.push(null); // End the stream
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
