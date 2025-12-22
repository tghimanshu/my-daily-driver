export interface GitHubEvent {
  id: string;
  type: string;
  actor: {
    login: string;
    avatar_url: string;
  };
  repo: {
    name: string;
    url: string;
  };
  created_at: string;
  payload: any;
}

export interface ContributionDay {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
}

export async function fetchGitHubActivity(
  username?: string
): Promise<GitHubEvent[]> {
  const token = process.env.GITHUB_TOKEN;
  const user = username || "himanshu-gohil";

  if (!token) {
    console.warn("GitHub token not configured");
    return [];
  }

  try {
    const res = await fetch(
      `https://api.github.com/users/${user}/events?per_page=30`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github.v3+json",
        },
        next: { revalidate: 600 }, // Cache for 10 mins
      }
    );

    if (!res.ok) {
      console.error(`GitHub API Error: ${res.status} ${res.statusText}`);
      return [];
    }

    const data = await res.json();
    return data;
  } catch (e) {
    console.error("GitHub API Error:", e);
    return [];
  }
}

export async function fetchContributionData(
  username?: string
): Promise<ContributionDay[]> {
  const token = process.env.GITHUB_TOKEN;
  const user = username || "himanshu-gohil";

  if (!token) return [];

  try {
    // Use GraphQL API to get contribution data
    const query = `
            query($userName:String!) {
                user(login: $userName){
                    contributionsCollection {
                        contributionCalendar {
                            totalContributions
                            weeks {
                                contributionDays {
                                    contributionCount
                                    date
                                }
                            }
                        }
                    }
                }
            }
        `;

    const res = await fetch("https://api.github.com/graphql", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        variables: { userName: user },
      }),
      next: { revalidate: 3600 }, // Cache for 1 hour
    });

    if (!res.ok) return [];

    const data = await res.json();
    const weeks =
      data?.data?.user?.contributionsCollection?.contributionCalendar?.weeks ||
      [];

    const contributions: ContributionDay[] = [];
    weeks.forEach((week: any) => {
      week.contributionDays.forEach((day: any) => {
        const level =
          day.contributionCount === 0
            ? 0
            : day.contributionCount <= 3
            ? 1
            : day.contributionCount <= 6
            ? 2
            : day.contributionCount <= 9
            ? 3
            : 4;

        contributions.push({
          date: day.date,
          count: day.contributionCount,
          level: level as 0 | 1 | 2 | 3 | 4,
        });
      });
    });

    return contributions;
  } catch (e) {
    console.error("GitHub Contributions API Error:", e);
    return [];
  }
}

export async function fetchGitHubStats(username?: string) {
  const token = process.env.GITHUB_TOKEN;
  const user = username || "himanshu-gohil";

  if (!token) return null;

  try {
    const res = await fetch(`https://api.github.com/users/${user}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
      next: { revalidate: 3600 },
    });

    if (!res.ok) return null;
    const data = await res.json();

    return {
      name: data.name,
      login: data.login,
      avatar: data.avatar_url,
      bio: data.bio,
      publicRepos: data.public_repos,
      followers: data.followers,
      following: data.following,
    };
  } catch (e) {
    console.error("GitHub Stats Error:", e);
    return null;
  }
}
