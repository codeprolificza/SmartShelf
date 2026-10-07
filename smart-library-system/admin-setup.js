function setupDefaultAdmins() {

    let accounts =
        JSON.parse(
            localStorage.getItem("ufh_accounts") || "[]"
        );


    // =========================
    // ADMIN 1
    // =========================

    const adminExists =
        accounts.some(
            account =>
                account.email === "10001@ufh.ac.za"
        );


    if (!adminExists) {

        accounts.push({

            name: "System Administrator",

            email: "10001@ufh.ac.za",

            password: "Admin@123",

            role: "admin",

            status: "approved"

        });

    }


    // =========================
    // ADMIN 2
    // =========================

    const secondAdminExists =
        accounts.some(
            account =>
                account.email === "10002@ufh.ac.za"
        );


    if (!secondAdminExists) {

        accounts.push({

            name: "Library Administrator",

            email: "10002@ufh.ac.za",

            password: "Admin@456",

            role: "admin",

            status: "approved"

        });

    }


    // =========================
    // SAVE
    // =========================

    localStorage.setItem(
        "ufh_accounts",
        JSON.stringify(accounts)
    );

}